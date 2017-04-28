# Chef Compliance Prometheus Exporter

# FAQ

### Why Python but not Go ?
Limited time and my familiarity to Python instead of Go Lang.

### Why do you fetch scan results in every *n* seconds ?
It is required to fetch latest scan results of every node, and it is possible to initiate a scan in Chef Compliance excluding some of the hosts. That is why, you need to start finding scan results in a *last*->*first* order to find a *latest* scan result for every host. Exporter fetchs the latest scan, mark the nodes that has results, then continues to fetch other scan results till it has a result for every node.

### What happens when a host is just entered in Chef Compliance but not scanned ?
This is the worst case scenario which leads exporter to check every scan result to find a data about that particular host. It won't have any major problems than having metrics available in a bit delayed fashion. This is the only reason why this exporter runs asyncronously in 2 threads. One for collector, one for http server.

### How can I find my `REFRESH_TOKEN` in Chef Compliance ?
Click your username icon on top right of the page, then you can obtain it from the `About` dialogue.

### How can I contribute ?
[Contribute](CONTRIBUTE.md)