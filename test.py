
import json
import pprint

nodes = json.load(open("in-old/nodes.json"))
n = {}
for t in nodes['nodes']:
	n[t['nodeinfo']['node_id']] = t
	t['statistics']['clients'] = {}
	t['firstseen'] += '+0000'
	t['lastseen'] += '+0000'

nodes['nodes'] = n

nodes = open("state.json.new", "w").write(json.dumps(nodes))
