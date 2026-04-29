import urllib.request
import json

req = urllib.request.Request('http://127.0.0.1:8010/api/cookies', method='DELETE')
urllib.request.urlopen(req)

# re-save cookies
cookies={'c_user':'100001507578295','xs':'36%3AZ2rivvWChEm5ig%3A2%3A1774131973%3A-1%3A-1%3A%3AAcx2XNNEPGPa6rI3mJx6TlPjSg-ESJSyal4r6cufCj0','datr':'Nz64aYMMP8F_Y661h407WAid','fr':'13nm5nPXqefWUu41S.AWerW_cac4O8Q-_tf1jaA60ZBMwL-3cbRJv6UKUy1BQ2_KidZ8o.Bp6R9c..AAA.0.0.Bp6R9c.AWfG6YxwmF62qX5w8Chu2g1XwAQ','sb':'Nz64aUbuUeVQs-eQDBQmzFI2'}
req_c = urllib.request.Request('http://127.0.0.1:8010/api/cookies', data=json.dumps({"cookies_dict": cookies}).encode(), headers={'Content-Type':'application/json'}, method='POST')
urllib.request.urlopen(req_c)

req2 = urllib.request.Request('http://127.0.0.1:8010/api/count-exact', data=json.dumps({"query":"notebook gamer","limit":200}).encode(), headers={'Content-Type':'application/json'}, method='POST')
r2 = urllib.request.urlopen(req2, timeout=120)
data = json.loads(r2.read())
bd = data.get('filter_breakdown', {})
print('captured:', bd.get('captured_raw'))
print('pagination doc_id:', bd.get('pagination', {}).get('doc_id_found'))
print('pagination pages:', bd.get('pagination', {}).get('pages_fetched'))
