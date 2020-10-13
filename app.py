import os
import time
from datetime import datetime
import json
import logging
import http.client
import base64
import nomad  # pylint: disable=E0401
import consul  # pylint: disable=E0401

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)


def clear_input_list(in_list):
    while "" in in_list:
        in_list.remove("")
    while "None" in in_list:
        in_list.remove("None")


def consul_put(c_consul, key, value):
    logger.debug("Put key: {} and value: {} to consul".format(key, value))
    return c_consul.kv.put(key, base64.urlsafe_b64encode(json.dumps(value).encode('utf-8')))


def consul_get(c_consul, key):
    index, data = c_consul.kv.get(key)
    if data:
        if data["Value"]:
            logger.debug("Get key: {} and value: {} from consul".format(key, data["Value"]))
            return json.loads(base64.urlsafe_b64decode(data["Value"]).decode('utf-8'))
    else:
        c_consul.kv.put(key, [])
        return []


def get_alloc_events(c_nomad, sent_events_list, node_name_list, job_id_list, event_types_list, event_message_filters):
    alloc_events = []
    allocations = c_nomad.allocations.get_allocations()
    logger.info("Get {} allocations".format(len(allocations)))
    for allocation in allocations:
        logger.debug("Raw allocation: {}".format(allocation))
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
                        logger.debug("Filtered alloc event: {}".format(alloc_event))
                        alloc_events.append(alloc_event)
    current_alloc_events = [evt for evt in alloc_events if evt not in sent_events_list]
    logger.debug("Current alloc_events: {}".format(current_alloc_events))
    return current_alloc_events


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
    logger.debug("Posting message to {}:\n{}".format(hook_url, message))
    if hook_url == "":
        return False
    headers = {"Content-type": "application/json"}
    connection = http.client.HTTPSConnection("hooks.slack.com")
    connection.request("POST", hook_url.replace("https://hooks.slack.com", ""), message, headers)
    if connection.getresponse().read().decode() == "ok":
        return True
    else:
        raise ConnectionError


def main():
    sent_events = []
    if os.getenv("NOMAD_EVENTS_TO_SLACK_DEBUG", "false") == "true":
        logger.setLevel(logging.DEBUG)
        logging.basicConfig(level=logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
        logging.basicConfig(level=logging.INFO)
    logger.info("Start APP. Reading ENV...")
    use_consul = os.getenv("USE_CONSUL", "false")
    consul_key = str(os.getenv("CONSUL_KEY", "nomad/nomad-events-to-slack"))
    node_names = str(os.getenv("NODE_NAMES", "")).split(",")
    job_ids = str(os.getenv("JOB_IDS", "")).split(",")
    event_types = str(os.getenv("EVENT_TYPES", "")).split(",")
    event_message_filters = str(os.getenv("EVENT_MESSAGE_FILTERS", "")).split(",")
    slack_web_hook_url = os.getenv("SLACK_WEB_HOOK_URL", "")
    if slack_web_hook_url == "":
        logger.error("ENV SLACK_WEB_HOOK_URL is not set. Set it to non-empty string and try again")
        raise EnvironmentError()
    clear_input_list(node_names)
    clear_input_list(job_ids)
    clear_input_list(event_types)
    clear_input_list(event_message_filters)
    my_nomad = nomad.Nomad()
    my_consul = consul.Consul()
    logger.info("ENV is ok. Start Loop.")
    while True:
        if use_consul == "true":
            try:
                sent_events = consul_get(my_consul, consul_key)
            except Exception:
                logger.error("Can't get value from Consul. Consul unavailable.")
                raise SystemExit()
        try:
            events = get_alloc_events(my_nomad, sent_events, node_names, job_ids, event_types, event_message_filters)
        except Exception:
            logger.error("Can't get info from Nomad. Nomad unavailable.")
            raise SystemExit()
        logger.info("Get {} new events".format(len(events)))
        for event in events:
            logger.debug("Event to Send: {}".format(event))
            try:
                slack_result = post_message_to_slack(slack_web_hook_url,
                                                     format_event_to_slack_message(event))
            except Exception:
                logger.error("Can't send message to Slack. Slack web hook url wrong.")
                raise SystemExit()
            if slack_result:
                sent_events.append(event)
                if use_consul == "true":
                    try:
                        consul_put(my_consul, consul_key, sent_events)
                    except Exception:
                        logger.error("Can't put value to Consul. Consul unavailable.")
                        raise SystemExit()
        logger.info("Send {} events. Wait 30 sec and check again".format(len(sent_events)))
        time.sleep(30)


if __name__ == "__main__":
    main()
