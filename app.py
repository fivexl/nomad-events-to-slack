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


def consul_put(key, value):
    # TODO: Consul is not running
    my_consul = consul.Consul()
    my_consul.kv.put(key, base64.urlsafe_b64encode(json.dumps(value).encode('utf-8')))


def consul_get(key):
    # TODO: Consul is not running
    my_consul = consul.Consul()
    index, data = my_consul.kv.get(key)
    if data:
        if data["Value"]:
            return json.loads(base64.urlsafe_b64decode(data["Value"]).decode('utf-8'))
    return []


# TODO: Def arg is mutable
def get_alloc_events(sent_events_list=[], node_name_list=[], job_id_list=[], event_types_list=[]):
    messages = []
    # TODO: Nomad is not running
    my_nomad = nomad.Nomad()
    allocations = my_nomad.allocations.get_allocations()
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
    # NOMAD ENV
    print("NOMAD_ADDR:", os.environ.get("NOMAD_ADDR"))
    print("NOMAD_NAMESPACE:", os.environ.get("NOMAD_NAMESPACE"))
    print("NOMAD_TOKEN:", os.environ.get("NOMAD_TOKEN"))
    print("NOMAD_REGION:", os.environ.get("NOMAD_REGION"))
    # EVENT FILTER ENV
    print("NODE_NAMES:", os.environ.get("NODE_NAMES"))
    print("JOB_IDS:", os.environ.get("JOB_IDS"))
    print("EVENT_TYPES:", os.environ.get("EVENT_TYPES"))
    # CONSUL ENV
    print("USE_CONSUL:", os.environ.get("USE_CONSUL"))
    # SLACK ENV
    print("SLACK_TOKEN:", os.environ.get("SLACK_TOKEN"))
    print("SLACK_CHANNEL:", os.environ.get("SLACK_CHANNEL"))
    print("SLACK_ICON_URL:", os.environ.get("SLACK_ICON_URL"))
    print("SLACK_USERNAME:", os.environ.get("SLACK_USERNAME"))
    node_names = str(os.environ.get("NODE_NAMES")).split(",")
    job_ids = str(os.environ.get("JOB_IDS")).split(",")
    event_types = str(os.environ.get("EVENT_TYPES")).split(",")
    clear_input_list(node_names)
    clear_input_list(job_ids)
    clear_input_list(event_types)
    use_consul = bool(os.environ.get("USE_CONSUL"))
    use_consul = True
    if use_consul and len(sent_events) == 0:
        sent_events = consul_get("nomad-scan-and-notify")
    while True:
        events = get_alloc_events(sent_events_list=sent_events, node_name_list=node_names, job_id_list=job_ids,
                                  event_types_list=event_types)
        for event in events:
            print("Event to Send:", event)
            # post_message_to_slack()
            # if message to slack is OK
            sent_events.append(event)
            if len(sent_events) != 0:
                consul_put("nomad-scan-and-notify", sent_events)
        print("Next Check after 5 sec!")
        time.sleep(5)


if __name__ == "__main__":
    main()
