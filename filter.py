#!/usr/bin/python3
# -*- coding: utf-8; -*-

import json
import os
import os.path
import sys


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
    online = True
    if 'flags' in n and 'online' in n['flags'] and not n['flags']['online']:
        online = False

    if online is False and 'hostname' in n['nodeinfo'] and \
       n['nodeinfo']['hostname'].startswith("ffv-"):
        return False

    return True


def get_nodes_validity(nodes):
    return {n['nodeinfo']['node_id']: valid_node(n) for n in nodes['nodes']}


def filter_nodes(nodes, valid_nodes):
    # only save valid nodes
    nodes_ffv = filter(lambda n: valid_nodes[n['nodeinfo']['node_id']],
                       nodes['nodes'])

    nodes['nodes'] = list(nodes_ffv)


def filter_meshviewer(meshviewer, valid_nodes):
    # only save valid nodes
    nodes_ffv = filter(lambda n: n['node_id'] in valid_nodes and valid_nodes[n['node_id']],
                       meshviewer['nodes'])
    meshviewer['nodes'] = list(nodes_ffv)

    nodes_src = filter(lambda n: valid_nodes[n['source']], meshviewer['links'])
    nodes_dst = filter(lambda n: valid_nodes[n['target']], nodes_src)
    meshviewer['links'] = list(nodes_dst)


def filter_nodelist(nodelist, valid_nodes):
    nodes_ffv = filter(lambda n:
                       n['id'] in valid_nodes and valid_nodes[n['id']],
                       nodelist['nodes'])

    nodelist['nodes'] = list(nodes_ffv)


def add_gw_nexthop(nodes, meshviewer):
    nexthops_id = {}
    for n in meshviewer['nodes']:
        if 'gateway_nexthop' not in n:
            continue

        if 'node_id' not in n:
            continue

        nexthops_id[n['node_id']] = n['gateway_nexthop']

    gw_id = {}
    for n in meshviewer['nodes']:
        if 'gateway' not in n:
            continue

        if 'node_id' not in n:
            continue

        gw_id[n['node_id']] = n['gateway']

    # prepare mapping of interface mac to "primary" mac
    primary_mac_mapping = {}
    for n in nodes['nodes']:
        if 'nodeinfo' not in n:
            continue

        if 'node_id' not in n['nodeinfo']:
            continue

        node_id = n['nodeinfo']['node_id']

        if 'network' not in n['nodeinfo']:
            continue

        if 'mac' not in n['nodeinfo']['network']:
            continue

        primary_mac_mapping[node_id] = n['nodeinfo']['network']['mac']

    for n in nodes['nodes']:
        if 'nodeinfo' not in n:
            continue

        if 'node_id' not in n['nodeinfo']:
            continue

        if 'statistics' not in n:
            continue

        if n['nodeinfo']['node_id'] in gw_id:
            node_gw_id = gw_id[n['nodeinfo']['node_id']]
            if node_gw_id not in primary_mac_mapping:
                continue

            n['statistics']['gateway'] = primary_mac_mapping[node_gw_id]

        if n['nodeinfo']['node_id'] in nexthops_id:
            node_gw_id = nexthops_id[n['nodeinfo']['node_id']]
            if node_gw_id not in primary_mac_mapping:
                continue

            nexthop = primary_mac_mapping[node_gw_id]
            n['statistics']['gateway_nexthop'] = nexthop


def add_uplink(nodes):
    for n in nodes['nodes']:
        if 'flags' not in n:
            continue

        n['flags']['uplink'] = False

        if 'statistics' not in n:
            continue

        if 'gateway' not in n['statistics']:
            continue

        if 'gateway_nexthop' not in n['statistics']:
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
        if 'node_id' not in n:
            continue
        if 'mac' not in n:
            continue

        primary_mac_mapping[n['node_id']] = n['mac']

    pos = 0
    for l in meshviewer['links']:
        if 'source' not in l:
            continue
        if 'source_tq' not in l:
            continue
        if 'target' not in l:
            continue
        if 'target_tq' not in l:
            continue
        if 'type' not in l:
            continue

        if l['source'] not in primary_mac_mapping:
            continue

        if l['target'] not in primary_mac_mapping:
            continue

        src = (l['source'], primary_mac_mapping[l['source']])
        dst = (l['target'], primary_mac_mapping[l['target']])

        if src not in endpoints_map:
            endpoints.append({
                "node_id": src[0],
                "id": src[1],
            })
            endpoints_map[src] = pos
            pos += 1

        if dst not in endpoints_map:
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
            "key": 0,
            "source": endpoints_map[src],
            "target": endpoints_map[dst],
            "tq": 1. / l['source_tq'],
            "type": mapped_type,
        })

        links.append({
            "key": 0,
            "source": endpoints_map[dst],
            "target": endpoints_map[src],
            "tq": 1. / l['target_tq'],
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
