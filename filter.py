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

def filter_graph(graph, valid_nodes):
	orig_pos = 0
	new_pos = 0
	pos_map = {}

	# calculate new list of nodes but first create mapping for old to new node index
	for n in graph['batadv']['nodes']:
		if 'node_id' in n and n['node_id'] in valid_nodes and valid_nodes[n['node_id']]:
			pos_map[orig_pos] = new_pos
			new_pos += 1
		orig_pos += 1

	nodes_ffv = filter(lambda n:'node_id' in n and n['node_id'] in valid_nodes and valid_nodes[n['node_id']], graph['batadv']['nodes'])
	graph['batadv']['nodes'] = list(nodes_ffv)

	# filter links with their new ids
	new_links = []
	for l in graph['batadv']['links']:
		if not l['source'] in pos_map:
			continue

		if not l['target'] in pos_map:
			continue

		l['source'] = pos_map[l['source']]
		l['target'] = pos_map[l['target']]

		new_links.append(l)

	graph['batadv']['links'] = new_links

def filter_nodelist(nodelist, valid_nodes):
	nodes_ffv = filter(lambda n: n['id'] in valid_nodes and valid_nodes[n['id']], nodelist['nodes'])

	nodelist['nodes'] = list(nodes_ffv)

def get_ifmac_types(nodes):
	mactypes = {}

	for n in nodes['nodes']:
		if not 'nodeinfo' in n:
			continue

		if not 'node_id' in n['nodeinfo']:
			continue

		if not 'network' in n['nodeinfo']:
			continue

		if not 'mesh' in n['nodeinfo']['network']:
			continue

		mesh = n['nodeinfo']['network']['mesh']
		for meshif in mesh:
			if not 'interfaces' in mesh[meshif]:
				continue

			interfaces = mesh[meshif]['interfaces']
			for t in interfaces:
				for mac in interfaces[t]:
					mactypes[mac] = t

	return mactypes

def map_graph_link_types(graph, mactypes):
	if not 'batadv' in graph:
		return

	if not 'links' in graph['batadv']:
		return

	links = graph['batadv']['links']

	# assigning type
	for l in links:
		mac_dst = l.get('dst')
		mac_src = l.get('src')

		td = None
		if mac_dst in mactypes:
			td = mactypes[mac_dst]

		ts = None
		if mac_src in mactypes:
			ts = mactypes[mac_src]

		if ts == 'l2tp' or td == 'l2tp':
			l['type'] = 'tunnel'
		elif ts == 'fastd' or td == 'fastd':
			l['type'] = 'tunnel'
		elif ts == 'tunnel' or td == 'tunnel':
			l['type'] = 'tunnel'
		elif td:
			l['type'] = td

	# cleanup
	for l in links:
		if 'dst' in l:
			del(l['dst'])

		if 'src' in l:
			del(l['src'])

		# remove VPN info when we have tunnel type
		if 'type' in l and 'vpn' in l:
			del(l['vpn'])

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

def filter_json(graph, nodes, nodelist, meshviewer):
	valid_nodes = get_nodes_validity(nodes)

	filter_nodes(nodes, valid_nodes)
	filter_graph(graph, valid_nodes)
	filter_meshviewer(meshviewer, valid_nodes)
	add_gw_nexthop(nodes, meshviewer)
	filter_nodelist(nodelist, valid_nodes)

	mactypes = get_ifmac_types(nodes)
	map_graph_link_types(graph, mactypes)

def main():
	if len(sys.argv) != 3:
		print("./filter INPATH OUTPATH")
		sys.exit(1)

	inpath = sys.argv[1]
	outpath = sys.argv[2]

	graph_in = os.path.join(inpath, "graph.json")
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
	graph = json.load(open(graph_in))
	nodes = json.load(open(nodes_in))
	nodelist = json.load(open(nodelist_in))
	meshviewer = json.load(open(meshviewer_in))

	filter_json(graph, nodes, nodelist, meshviewer)

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
