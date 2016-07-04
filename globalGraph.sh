#! /bin/sh

NODEDBPATH=${1:-"./nodes.rrd"}
OUTIMAGE=${2:-"./globalGraph.png"}

rrdtool graph "${OUTIMAGE}" \
	-s -14d \
        -w 1000 \
        -h  600 \
        'DEF:nodes='"${NODEDBPATH}"':nodes:AVERAGE' \
        'LINE1:nodes#F00:nodes\l' \
        'DEF:clients='"${NODEDBPATH}"':clients:AVERAGE' \
        'LINE2:clients#00F:clients'
