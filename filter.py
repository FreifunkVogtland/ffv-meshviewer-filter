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

def drop_contact_info(n):
	if 'owner' in n:
		del(n['owner'])
	return n

def filter_nodes(nodes, valid_nodes):
	# filter contact info due to privacy concerns
	nodes_priv = map(drop_contact_info, nodes['nodes'])

	# only save valid nodes
	nodes_ffv = filter(lambda n: valid_nodes[n['nodeinfo']['node_id']], nodes_priv)

	nodes['nodes'] = list(nodes_ffv)

	# remove owner information
	for n in nodes['nodes']:
		if not 'nodeinfo' in n:
			continue

		if not 'owner' in n['nodeinfo']:
			continue

		del n['nodeinfo']['owner']

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

def map_gateway_addresses(nodes, graph, valid_nodes):
	graph_mappings = {}

	# find macs which are known by graph.json for each node_id
	for n in graph['batadv']['nodes']:
		if not 'id' in n:
			continue

		if not 'node_id' in n:
			continue

		graph_mappings[n['node_id']] = n['id']

	# prepare mapping of interface mac to "primary" mac
	primary_mac_mapping = {}
	for n in nodes['nodes']:
		if not 'nodeinfo' in n:
			continue

		if not 'node_id' in n['nodeinfo']:
			continue

		node_id = n['nodeinfo']['node_id']
		if not node_id in graph_mappings:
			continue

		if not 'network' in n['nodeinfo']:
			continue

		if not 'mesh_interfaces' in n['nodeinfo']['network']:
			continue

		mesh_interfaces = n['nodeinfo']['network']['mesh_interfaces']

		for mac in mesh_interfaces:
			if mac in graph_mappings:
				continue

			primary_mac_mapping[mac] = graph_mappings[node_id]

	# convert gateway and gateway_nexthop to its graph.json "primary_mac"
	for n in nodes['nodes']:
		if not 'statistics' in n:
			continue

		if 'gateway' in n['statistics']:
			gateway = n['statistics']['gateway']
			if gateway in primary_mac_mapping:
				gateway = primary_mac_mapping[gateway]

			n['statistics']['gateway'] = gateway

		if 'gateway_nexthop' in n['statistics']:
			gateway_nexthop = n['statistics']['gateway_nexthop']
			if gateway_nexthop in primary_mac_mapping:
				gateway_nexthop = primary_mac_mapping[gateway_nexthop]

			n['statistics']['gateway_nexthop'] = gateway_nexthop

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
		mac_src = l.get('dst')

		td = None
		if mac_dst in mactypes:
			td = mactypes[mac_dst]

		ts = None
		if mac_src in mactypes:
			ts = mactypes[mac_src]

		if ts == 'l2tp' or td == 'l2tp':
			l['type'] = 'l2tp'
		elif ts == 'fastd' or td == 'fastd':
			l['type'] = 'fastd'
		elif ts == 'tunnel' or td == 'tunnel':
			l['type'] = 'fastd'
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

def filter_json(graph, nodes, nodelist):
	valid_nodes = get_nodes_validity(nodes)

	# force server brewster with old ffnord-alfred-announce to be part of FFV
	valid_nodes['7446a06579d2'] = True

	# force server newton with old ffnord-alfred-announce to be part of FFV
	valid_nodes['001d92340f69'] = True

	# force server pascal with old ffnord-alfred-announce to be part of FFV
	valid_nodes['e89a8f508b7b'] = True

	filter_nodes(nodes, valid_nodes)
	filter_graph(graph, valid_nodes)
	map_gateway_addresses(nodes, graph, valid_nodes)
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

	# load
	graph = json.load(open(graph_in))
	nodes = json.load(open(nodes_in))
	nodelist = json.load(open(nodelist_in))

	filter_json(graph, nodes, nodelist)

	# save
	dump_json(graph, graph_outtmp)
	dump_json(nodes, nodes_outtmp)
	dump_json(nodelist, nodelist_outtmp)

	os.rename(graph_outtmp, graph_out)
	os.rename(nodes_outtmp, nodes_out)
	os.rename(nodelist_outtmp, nodelist_out)

if __name__ == "__main__":
	main()
