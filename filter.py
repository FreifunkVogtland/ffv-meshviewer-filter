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

def valid_node(n):
	# is vpn?
	if 'vpn' in n['nodeinfo'] and n['nodeinfo']['vpn']:
		return True

	# node with default config offline?
	online = True;
	if 'flags' in n and 'online' in n['flags'] and not n['flags']['online']:
		online = False

	if online == False and 'hostname' in n['nodeinfo'] and n['nodeinfo']['hostname'].startswith("ffv-"):
		return False

	return True

def get_nodes_validity(nodes):
	return {n['nodeinfo']['node_id']: valid_node(n) for n in nodes['nodes']}

def filter_nodes(nodes, valid_nodes):
	# only save valid nodes
	nodes_ffv = filter(lambda n: valid_nodes[n['nodeinfo']['node_id']], nodes['nodes'])

	nodes['nodes'] = list(nodes_ffv)

def filter_meshviewer(meshviewer, valid_nodes):
	# only save valid nodes
	nodes_ffv = filter(lambda n: valid_nodes[n['node_id']], meshviewer['nodes'])
	meshviewer['nodes'] = list(nodes_ffv)

	nodes_src = filter(lambda n: valid_nodes[n['source']], meshviewer['links'])
	nodes_dst = filter(lambda n: valid_nodes[n['target']], nodes_src)
	meshviewer['links'] = list(nodes_dst)

def filter_nodelist(nodelist, valid_nodes):
	nodes_ffv = filter(lambda n: n['id'] in valid_nodes and valid_nodes[n['id']], nodelist['nodes'])

	nodelist['nodes'] = list(nodes_ffv)

def add_gw_nexthop(nodes, meshviewer):
	nexthops_id = {}
	for n in meshviewer['nodes']:
		if not 'gateway_nexthop' in n:
			continue

		if not 'node_id' in n:
			continue

		nexthops_id[n['node_id']] = n['gateway_nexthop']

	gw_id = {}
	for n in meshviewer['nodes']:
		if not 'gateway' in n:
			continue

		if not 'node_id' in n:
			continue

		gw_id[n['node_id']] = n['gateway']

	# prepare mapping of interface mac to "primary" mac
	primary_mac_mapping = {}
	for n in nodes['nodes']:
		if not 'nodeinfo' in n:
			continue

		if not 'node_id' in n['nodeinfo']:
			continue

		node_id = n['nodeinfo']['node_id']

		if not 'network' in n['nodeinfo']:
			continue

		if not 'mac' in n['nodeinfo']['network']:
			continue

		primary_mac_mapping[node_id] = n['nodeinfo']['network']['mac']

	for n in nodes['nodes']:
		if not 'nodeinfo' in n:
			continue

		if not 'node_id' in n['nodeinfo']:
			continue

		if not 'statistics' in n:
			continue

		if n['nodeinfo']['node_id'] in gw_id:
			node_gw_id = gw_id[n['nodeinfo']['node_id']]
			if not node_gw_id in primary_mac_mapping:
				continue

			n['statistics']['gateway'] = primary_mac_mapping[node_gw_id]

		if n['nodeinfo']['node_id'] in nexthops_id:
			node_gw_id = nexthops_id[n['nodeinfo']['node_id']]
			if not node_gw_id in primary_mac_mapping:
				continue

			n['statistics']['gateway_nexthop'] = primary_mac_mapping[node_gw_id]

def add_uplink(nodes):
	for n in nodes['nodes']:
		if not 'flags' in n:
			continue

		n['flags']['uplink'] = False

		if not 'statistics' in n:
			continue

		if not 'gateway' in n['statistics']:
			continue

		if not 'gateway_nexthop' in n['statistics']:
			continue

		# TODO maybe it is better to check the graph for links with type 'vpn'
		if n['statistics']['gateway'] != n['statistics']['gateway_nexthop']:
			continue

		n['flags']['uplink'] = True


def extract_graph(meshviewer):
	graph = {
		"version": 1,
		"batadv": {
			"multigraph": True,
			"graph": {},
			"directed": True,
			"nodes": [],
			"links": [],
		},
	}

	endpoints_map = {}
	endpoints = graph['batadv']['nodes']
	links = graph['batadv']['links']

	# prepare mapping of interface mac to "primary" mac
	primary_mac_mapping = {}
	for n in meshviewer['nodes']:
		if not 'node_id' in n:
			continue
		if not 'mac' in n:
			continue

		primary_mac_mapping[n['node_id']] = n['mac']


	pos = 0
	for l in meshviewer['links']:
		if not 'source' in l:
			continue
		if not 'source_mac' in l:
			continue
		if not 'source_tq' in l:
			continue
		if not 'target' in l:
			continue
		if not 'target_mac' in l:
			continue
		if not 'target_tq' in l:
			continue
		if not 'type' in l:
			continue

		if not l['source'] in primary_mac_mapping:
			continue

		if not l['target'] in primary_mac_mapping:
			continue

		src = (l['source'], primary_mac_mapping[l['source']])
		dst = (l['target'], primary_mac_mapping[l['target']])

		if not src in endpoints_map:
			endpoints.append({
				"node_id": src[0],
				"id": src[1],
			})
			endpoints_map[src] = pos
			pos += 1

		if not dst in endpoints_map:
			endpoints.append({
				"node_id": dst[0],
				"id": dst[1],
			})
			endpoints_map[dst] = pos
			pos += 1

		if l['target_tq'] <= 0:
			l['target_tq'] = 0.01

		if l['source_tq'] <= 0:
			l['source_tq'] = 0.01


		if l["type"] == "vpn":
			mapped_type = "tunnel"
		elif l["type"] == "wifi":
			mapped_type = "wireless"
		else:
			mapped_type = l["type"]

		links.append({
			"key" : 0,
			"source" : endpoints_map[src],
			"target" : endpoints_map[dst],
			"tq" : 1. / l['source_tq'],
			"type": mapped_type,
		})

		links.append({
			"key" : 0,
			"source" : endpoints_map[dst],
			"target" : endpoints_map[src],
			"tq" : 1. / l['target_tq'],
			"type": mapped_type,
		})

	return graph

def filter_json(nodes, nodelist, meshviewer):
	valid_nodes = get_nodes_validity(nodes)

	filter_nodes(nodes, valid_nodes)
	filter_meshviewer(meshviewer, valid_nodes)
	add_gw_nexthop(nodes, meshviewer)
	add_uplink(nodes)
	filter_nodelist(nodelist, valid_nodes)

def main():
	if len(sys.argv) != 3:
		print("./filter INPATH OUTPATH")
		sys.exit(1)

	inpath = sys.argv[1]
	outpath = sys.argv[2]

	graph_out = os.path.join(outpath, "graph.json")
	graph_outtmp = os.path.join(outpath, "graph.json.tmp")
	nodes_in = os.path.join(inpath, "nodes.json")
	nodes_out = os.path.join(outpath, "nodes.json")
	nodes_outtmp = os.path.join(outpath, "nodes.json.tmp")
	nodelist_in = os.path.join(inpath, "nodelist.json")
	nodelist_out = os.path.join(outpath, "nodelist.json")
	nodelist_outtmp = os.path.join(outpath, "nodelist.json.tmp")
	meshviewer_in = os.path.join(inpath, "meshviewer.json")
	meshviewer_out = os.path.join(outpath, "meshviewer.json")
	meshviewer_outtmp = os.path.join(outpath, "meshviewer.json.tmp")

	# load
	nodes = json.load(open(nodes_in))
	nodelist = json.load(open(nodelist_in))
	meshviewer = json.load(open(meshviewer_in))

	filter_json(nodes, nodelist, meshviewer)
	graph = extract_graph(meshviewer)

	# save
	dump_json(graph, graph_outtmp)
	dump_json(nodes, nodes_outtmp)
	dump_json(nodelist, nodelist_outtmp)
	dump_json(meshviewer, meshviewer_outtmp)

	os.rename(graph_outtmp, graph_out)
	os.rename(nodes_outtmp, nodes_out)
	os.rename(nodelist_outtmp, nodelist_out)
	os.rename(meshviewer_outtmp, meshviewer_out)

if __name__ == "__main__":
	main()
