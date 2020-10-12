# nomad-allocations-scan-and-notify

Example of Event to Send: 
```
{'Allocation ID': '4f5c9fe9-7087-e213-6830-fc8e924db354', 'NodeName': 'node1', 'JobID': 'oom-killed', 'JobType': 'service',
 'TaskGroup': 'oom-killed', 'TaskName': 'oom-task', 'Time': '2020-10-12 15:10:02', 'EventType': 'Not Restarting', 'EventMessage': '', 
 'EventDisplayMessage': 'Exceeded allowed attempts 2 in interval 30m0s and mode is "fail"', 'EventDetails': 
 {'restart_reason': 'Exceeded allowed attempts 2 in interval 30m0s and mode is "fail"', 'fails_task': 'true'}}
```
