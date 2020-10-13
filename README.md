# nomad-events-to-slack

## Example of Event to Send: 
```
{'AllocationID': '4f5c9fe9-7087-e213-6830-fc8e924db354', 'NodeName': 'node1', 'JobID': 'oom-killed', 'JobType': 'service',
 'TaskGroup': 'oom-killed', 'TaskName': 'oom-task', 'Time': '2020-10-12 15:10:02', 'EventType': 'Not Restarting', 'EventMessage': '', 
 'EventDisplayMessage': 'Exceeded allowed attempts 2 in interval 30m0s and mode is "fail"', 'EventDetails': 
 {'restart_reason': 'Exceeded allowed attempts 2 in interval 30m0s and mode is "fail"', 'fails_task': 'true'}}
```

## How to build and run with docker
- `cp .env.sample .env`
- `docker build -t nomad-events-to-slack:latest .`
- `docker run --net="host" --env-file .env nomad-events-to-slack:latest`

## Nomad Job for test notifications
```hcl
job "oom-killed" {
    datacenters = ["dc1"]
    type = "service"
    group "oom-killed" {
        task "oom-task" {
            driver = "docker"
            env {
                NODE_NAME="${node.unique.name}"
            }
            config {
                image = "zyfdedh/stress:latest"
                command = "sh"
                args = [ "-c", "sleep 10; stress --vm 1 --vm-bytes 50M" ]
            }
            resources {
                memory = 15 # MB
            }
        }
    }
}
```