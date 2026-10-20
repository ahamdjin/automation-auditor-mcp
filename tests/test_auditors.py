import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from automation_auditor_mcp.core import audit_workflow, supported_platforms


class AdapterTests(unittest.TestCase):
    def load(self, filename):
        return (ROOT / 'examples' / filename).read_text()

    def test_realistic_n8n_ok(self):
        report = audit_workflow('n8n', self.load('n8n-valid.json'))
        self.assertTrue(report['supported'])
        self.assertEqual(report['summary']['errors'], 0)
        self.assertEqual(report['status'], 'no_findings_detected')

    def test_n8n_broken_connections_and_webhook(self):
        r = audit_workflow('auto', self.load('n8n-broken.json'))
        self.assertEqual(r['platform'], 'n8n')
        self.assertEqual({x['rule'] for x in r['findings']}, {'N8N006','N8N009'})
        self.assertNotIn('Deleted step', json.dumps(r))

    def test_n8n_duplicate_node_and_missing_source(self):
        data = json.loads(self.load('n8n-valid.json'))
        data['nodes'].append(dict(data['nodes'][0]))
        data['connections']['deleted'] = {'main':[[]]}
        r = audit_workflow('n8n', json.dumps(data))
        self.assertTrue({'N8N004','N8N005','N8N007'} <= {x['rule'] for x in r['findings']})

    def test_dify_yaml_valid(self):
        r = audit_workflow('auto', self.load('dify-valid.yaml'))
        self.assertEqual(r['platform'], 'dify')
        self.assertEqual(r['summary']['total'], 0)

    def test_dify_dangling_and_duplicate(self):
        d = {'workflow':{'graph':{'nodes':[{'id':'s','data':{'type':'start'}},{'id':'s','data':{'type':'llm'}}], 'edges':[{'source':'s','target':'missing'}]}}}
        r = audit_workflow('dify', json.dumps(d))
        self.assertTrue({'DFY005','DFY007','DFY009'} <= {x['rule'] for x in r['findings']})

    def test_trigger_heuristic_only(self):
        r = audit_workflow('auto', self.load('trigger-demo.ts'))
        self.assertEqual(r['platform'],'trigger')
        self.assertEqual(r['summary']['errors'],0)
        self.assertIn('TRG099',{x['rule'] for x in r['findings']})

    def test_trigger_duplicate_task_id(self):
        source = """import { task } from "@trigger.dev/sdk";
        export const a = task({ id: "lead-retry", run: async () => {} });
        export const b = task({ id: "lead-retry", run: async () => {} });"""
        r = audit_workflow('trigger', source)
        self.assertIn('TRG004',{x['rule'] for x in r['findings']})
        self.assertNotIn('lead-retry',json.dumps(r))

    def test_activepieces_chain_and_invalid(self):
        payload = json.loads(self.load('activepieces-flow.json'))
        normal = audit_workflow('auto', json.dumps(payload))
        self.assertEqual(normal['platform'],'activepieces')
        self.assertEqual(normal['summary']['total'],0)
        payload['version']['trigger']['nextAction']['valid']=False
        payload['version']['trigger']['nextAction']['name']='trigger'
        broken = audit_workflow('activepieces',json.dumps(payload))
        self.assertEqual({x['rule'] for x in broken['findings']},{'AP004','AP006'})

    def test_unsupported_platform_is_not_clean(self):
        r = audit_workflow('make','{"scenario": []}')
        self.assertFalse(r['supported'])
        self.assertEqual(r['status'],'unsupported')

    def test_auto_unknown_is_not_clean(self):
        self.assertFalse(audit_workflow('auto','{"hello":"world"}')['supported'])

    def test_fail_on_duplicate_json_keys(self):
        r = audit_workflow('n8n','{"nodes":[],"connections":{},"nodes":[]}')
        self.assertEqual(r['summary']['errors'],1)
        self.assertEqual(r['findings'][0]['rule'],'GEN003')

    def test_fail_on_unsafe_yaml_aliases(self):
        r = audit_workflow('dify','a: &secret ["x"]\nb: *secret')
        self.assertEqual(r['summary']['errors'],1)

    def test_oversized_input_rejected_without_echo(self):
        with self.assertRaisesRegex(ValueError,'250000'):
            audit_workflow('n8n','x'*250001)

    def test_pii_not_duplicated_in_report(self):
        r=audit_workflow('n8n',json.dumps({'nodes':[{'name':'customer@example.com','id':'a','type':'webhook','parameters':{}},{'name':'customer@example.com','id':'a','type':'webhook','parameters':{}}],'connections':{}}))
        self.assertNotIn('customer@example.com',json.dumps(r))

    def test_platform_catalog_truthful(self):
        result = supported_platforms()
        self.assertEqual(len(result['native_adapters']),4)
        self.assertIn('heuristic',result['formats']['trigger'].lower())

if __name__ == '__main__': unittest.main()
