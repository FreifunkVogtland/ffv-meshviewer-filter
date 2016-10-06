#!/usr/bin/python
# -*- coding: utf-8; -*-

import sys
import os, os.path
import json

def dump_json(data, filename):
	with open(filename, 'w') as f:
		json.dump(data, f)
		f.flush()
		os.fsync(f.fileno())

def main():
	if len(sys.argv) != 3:
		print("./filter INPATH OUTPATH")
		sys.exit(1)

	inpath = sys.argv[1]
	outpath = sys.argv[2]

	nodes_in = os.path.join(inpath, "nodes.json")
	nodes_out = os.path.join(outpath, "nodes.json")
	nodes_outtmp = os.path.join(outpath, "nodes.json.tmp")

	# load
	nodes = json.load(open(nodes_in))

	for n in nodes['nodes']:
		if not 'nodeinfo' in n:
			continue

		nodeinfo = n['nodeinfo']

		if not 'software' in nodeinfo:
			continue

		software = nodeinfo['software']
		if not 'firmware' in software:
			continue

		firmware = software['firmware']

		if not 'release' in firmware:
			continue

		if not firmware['release'].endswith('-v'):
			continue

		n['lastseen'] = '2016-09-04T23:35:02'

	# save
	dump_json(nodes, nodes_outtmp)

	os.rename(nodes_outtmp, nodes_out)

if __name__ == "__main__":
	main()
