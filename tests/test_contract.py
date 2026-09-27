import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_map import read,normalise_edge,EDGE_KEYS
from validate import validate,route_graph
import networkx as nx

class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        allc=read('data/counties.json');e=read('data/connections.json')[0]
        cls.c=[c for c in allc if c['县编号'] in [e[EDGE_KEYS[0]],e[EDGE_KEYS[1]]]]
        cls.e=e
    def valid(self,c=None,e=None):
        return validate(c or self.c,e if e is not None else [self.e],spatial=False)
    def test_valid(self):self.assertEqual(self.valid()['status'],'PASS')
    def test_zero_not_null(self):
        e=dict(self.e);e[EDGE_KEYS[4]]=0
        with self.assertRaises(ValueError):self.valid(e=[e])
    def test_empty_string_not_null(self):
        e=dict(self.e);e[EDGE_KEYS[4]]=''
        with self.assertRaises(ValueError):self.valid(e=[e])
    def test_missing_land_type(self):
        e=dict(self.e);e[EDGE_KEYS[3]]=None
        with self.assertRaises(ValueError):self.valid(e=[e])
    def test_water_only_one_direction(self):
        e=dict(self.e);e.update({EDGE_KEYS[2]:None,EDGE_KEYS[3]:None,EDGE_KEYS[4]:10.,EDGE_KEYS[5]:None})
        self.valid(e=[e]);g=route_graph(self.c,[e],'water');a,b=e[EDGE_KEYS[0]],e[EDGE_KEYS[1]]
        self.assertTrue(nx.has_path(g,a,b));self.assertFalse(nx.has_path(g,b,a))
    def test_reverse_preserves_direction(self):
        e=dict(self.e);a,b=e[EDGE_KEYS[0]],e[EDGE_KEYS[1]]
        e.update({EDGE_KEYS[0]:b,EDGE_KEYS[1]:a,EDGE_KEYS[4]:7.,EDGE_KEYS[5]:None})
        n=normalise_edge(e);self.assertEqual(n[EDGE_KEYS[0]],a)
        self.assertIsNone(n[EDGE_KEYS[4]]);self.assertEqual(n[EDGE_KEYS[5]],7.)
    def test_duplicate_pair(self):
        with self.assertRaises(ValueError):self.valid(e=[self.e,self.e])
    def test_orphan(self):
        e=dict(self.e);e[EDGE_KEYS[1]]='NONEXISTENT'
        with self.assertRaises(ValueError):self.valid(e=[e])
    def test_area_mismatch(self):
        c=copy.deepcopy(self.c);c[0]['初始土地用途']['耕地']+=1
        with self.assertRaises(ValueError):self.valid(c=c)
    def test_population_bool(self):
        c=copy.deepcopy(self.c);c[0]['初始人口']=True
        with self.assertRaises(ValueError):self.valid(c=c)
    def test_invalid_resource(self):
        c=copy.deepcopy(self.c);c[0]['自然资源']=['木材']
        with self.assertRaises(ValueError):self.valid(c=c)
    def test_seat_outside(self):
        c=copy.deepcopy(self.c);c[0]['治所坐标']=[0,0]
        with self.assertRaises(ValueError):self.valid(c=c)
    def test_no_channels(self):
        e=dict(self.e)
        for k in EDGE_KEYS[2:]:e[k]=None
        with self.assertRaises(ValueError):self.valid(e=[e])
    def test_cart_restriction(self):
        e=dict(self.e);e[EDGE_KEYS[3]]='不能走车'
        self.assertEqual(route_graph(self.c,[e],'cart').number_of_edges(),0)
        self.assertEqual(route_graph(self.c,[e],'land').number_of_edges(),2)
    def test_nonfinite_distance(self):
        e=dict(self.e);e[EDGE_KEYS[4]]=float('nan')
        with self.assertRaises(ValueError):self.valid(e=[e])
if __name__=='__main__':unittest.main()
