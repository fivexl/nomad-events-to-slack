import nomad
import consul
import http.client
import json
import os
import time
import base64
from datetime import datetime


def clear_input_list(in_list):
    while "" in in_list:
        in_list.remove("")
    while "None" in in_list:
        in_list.remove("None")


def consul_put(c_consul, key, value):
    return c_consul.kv.put(key, base64.urlsafe_b64encode(json.dumps(value).encode('utf-8')))


def consul_get(c_consul, key):
    index, data = c_consul.kv.get(key)
    if data:
        if data["Value"]:
            return json.loads(base64.urlsafe_b64decode(data["Value"]).decode('utf-8'))
    return []


def get_alloc_events(c_nomad, sent_events_list, node_name_list, job_id_list, event_types_list, event_message_filters):
    alloc_events = []
    allocations = c_nomad.allocations.get_allocations()
    for allocation in allocations:
        if (allocation["NodeName"] in node_name_list and allocation["JobID"] in job_id_list) or \
                (allocation["NodeName"] in node_name_list and len(job_id_list) == 0) or \
                (len(node_name_list) == 0 and allocation["JobID"] in job_id_list) or \
                (len(node_name_list) == 0 and len(job_id_list) == 0):
            for task, state in allocation["TaskStates"].items():
                for event in state["Events"]:
                    if (event["Type"] in event_types_list and event["Message"] in event_message_filters) or \
                            (event["Type"] in event_types_list and len(event_message_filters) == 0) or \
                            (len(event_types_list) and event["Message"] in event_message_filters) or \
                            (len(event_types_list) == 0 and len(event_message_filters) == 0):
                        alloc_event = {
                            "AllocationID": allocation["ID"],
                            "NodeName": allocation["NodeName"],
                            "JobID": allocation["JobID"],
                            "JobType": allocation["JobType"],
                            "TaskGroup": allocation["TaskGroup"],
                            "TaskName": task,
                            "Time": datetime.utcfromtimestamp(float(event["Time"]) / 1000000000).strftime(
                                '%Y-%m-%d %H:%M:%S'),
                            "EventType": event["Type"],
                            "EventMessage": event["Message"],
                            "EventDisplayMessage": event["DisplayMessage"],
                            "EventDetails": event["Details"]
                        }
                        alloc_events.append(alloc_event)
    return [evt for evt in alloc_events if evt not in sent_events_list]


def format_event_to_slack_message(event):
    event_details = ""
    for key, value in event["EventDetails"].items():
        event_details += key + ": " + value + " "
    message = {
        "attachments": [{
            "color": "#36a64f",
            "footer": "Time: {}, AllocationID: {}".format(event["Time"], event["AllocationID"]),
            "fields": [
                {
                    "title": "New Event",
                    "value": "Task: {}\n EventType: {}".format(event["TaskName"], event["EventType"]),
                    "short": False
                },
                {
                    "title": "Task Info",
                    "value": "Message: {}\n DisplayMessage: {}".format(event["EventMessage"],
                                                                       event["EventDisplayMessage"]),
                    "short": False
                },
                {
                    "title": "Job Info",
                    "value": "NodeName: {}, JobID: {}, TaskGroup: {}, JobType: {}".format(event["NodeName"],
                                                                                          event["JobID"],
                                                                                          event["TaskGroup"],
                                                                                          event["JobType"]),
                    "short": True
                },
                {
                    "title": "Event Details",
                    "value": event_details,
                    "short": True
                }
            ]
        }]
    }
    return json.dumps(message)


def post_message_to_slack(hook_url, message):
    if hook_url == "":
        return False
    headers = {"Content-type": "application/json"}
    connection = http.client.HTTPSConnection("hooks.slack.com")
    connection.request("POST", hook_url.replace("https://hooks.slack.com", ""), message, headers)
    if connection.getresponse().read().decode() == "ok":
        return True
    else:
        return False


def main():
    sent_events = []
    use_consul = bool(os.getenv("USE_CONSUL", False))
    consul_key = str(os.getenv("CONSUL_KEY", "nomad/nomad-events-to-slack"))
    node_names = str(os.getenv("NODE_NAMES", "")).split(",")
    job_ids = str(os.getenv("JOB_IDS", "")).split(",")
    event_types = str(os.getenv("EVENT_TYPES", "")).split(",")
    event_message_filters = str(os.getenv("EVENT_MESSAGE_FILTERS", "")).split(",")
    clear_input_list(node_names)
    clear_input_list(job_ids)
    clear_input_list(event_types)
    clear_input_list(event_message_filters)
    my_nomad = nomad.Nomad()
    my_consul = consul.Consul()
    if use_consul and len(sent_events) == 0:
        try:
            sent_events = consul_get(my_consul, consul_key)
        except Exception:
            raise SystemExit("Can't get value from Consul. Consul unavailable.")
    while True:
        try:
            events = get_alloc_events(my_nomad, sent_events, node_names, job_ids, event_types, event_message_filters)
        except Exception:
            raise SystemExit("Can't get info from Nomad. Nomad unavailable.")
        for event in events:
            print("Event to Send:", event)
            try:
                slack_result = post_message_to_slack(os.getenv("SLACK_WEB_HOOK_URL"),
                                                     format_event_to_slack_message(event))
            except Exception:
                raise SystemExit("Can't send message to Slack. Slack web hook url wrong.")
            if slack_result:
                sent_events.append(event)
                if use_consul and len(sent_events) != 0:
                    try:
                        consul_put(my_consul, consul_key, sent_events)
                    except Exception:
                        raise SystemExit("Can't put value to Consul. Consul unavailable.")
        print("Next Check after 60 sec!")
        time.sleep(60)


if __name__ == "__main__":
    main()
