import nomad
import consul
import requests
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


# TODO: Def arg is mutable
def get_alloc_events(c_nomad, sent_events_list=[], node_name_list=[], job_id_list=[], event_types_list=[]):
    messages = []
    allocations = c_nomad.allocations.get_allocations()
    for allocation in allocations:
        if (allocation["NodeName"] in node_name_list and allocation["JobID"] in job_id_list) or \
                (allocation["NodeName"] in node_name_list and len(job_id_list) == 0) or \
                (len(node_name_list) == 0 and allocation["JobID"] in job_id_list) or \
                (len(node_name_list) == 0 and len(job_id_list) == 0):
            for task, state in allocation["TaskStates"].items():
                for event in state["Events"]:
                    if event["Type"] in event_types_list or len(event_types_list) == 0:
                        message = {
                            "Allocation ID": allocation["ID"],
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
                        messages.append(message)
    current_messages = [m for m in messages if m not in sent_events_list]
    return current_messages


def post_message_to_slack(token, channel, text, icon_url, username, blocks=None):
    return requests.post('https://slack.com/api/chat.postMessage', {
        'token': token,
        'channel': channel,
        'text': text,
        'icon_url': icon_url if icon_url else None,
        'username': username if username else None,
        'blocks': json.dumps(blocks) if blocks else None
    }).json()


def main():
    sent_events = []
    use_consul = bool(os.getenv("USE_CONSUL", False))
    consul_key = str(os.getenv("CONSUL_KEY", "nomad/nomad-events-to-slack"))
    node_names = str(os.getenv("NODE_NAMES", "")).split(",")
    job_ids = str(os.getenv("JOB_IDS", "")).split(",")
    event_types = str(os.getenv("EVENT_TYPES", "")).split(",")
    clear_input_list(node_names)
    clear_input_list(job_ids)
    clear_input_list(event_types)
    my_nomad = nomad.Nomad()
    my_consul = consul.Consul()
    if use_consul and len(sent_events) == 0:
        try:
            sent_events = consul_get(my_consul, consul_key)
        except Exception as err:
            raise SystemExit("Can't get value from Consul. Consul unavailable.")
    while True:
        try:
            events = get_alloc_events(my_nomad, sent_events, node_names, job_ids, event_types)
        except Exception as err:
            raise SystemExit("Can't get info from Nomad. Nomad unavailable.")
        for event in events:
            print("Event to Send:", event)
            slack_result = post_message_to_slack(os.getenv("SLACK_TOKEN"), os.getenv("SLACK_CHANNEL"), event,
                                                 os.getenv("SLACK_ICON_URL", ""),
                                                 os.getenv("SLACK_USERNAME", "NomadEventBot"))
            if slack_result["ok"]:
                sent_events.append(event)
                if use_consul and len(sent_events) != 0:
                    try:
                        consul_put(my_consul, consul_key, sent_events)
                    except Exception as err:
                        raise SystemExit("Can't put value to Consul. Consul unavailable.")
        print("Next Check after 5 sec!")
        time.sleep(5)


if __name__ == "__main__":
    main()
