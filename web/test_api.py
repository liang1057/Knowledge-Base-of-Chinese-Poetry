"""测试 API"""
import sys
sys.path.insert(0, 'D:/WorkBuddy/Knowledge-Base-of-Chinese-Poetry/web2')

from app import app
import json

app.config['TESTING'] = True

with app.test_client() as client:
    # 测试统计接口
    r = client.get('/api/stats')
    print('Stats:', r.status_code)
    if r.status_code == 200:
        print(json.loads(r.data))
    
    # 测试朝代接口
    r = client.get('/api/dynasties')
    print('\nDynasties:', r.status_code)
    if r.status_code == 200:
        dynasties = json.loads(r.data)
        print(f'Total: {len(dynasties)}')
        for d in dynasties[:3]:
            print(f'  - {d}')
        
        # 测试作者接口
        if dynasties:
            dynasty_id = dynasties[0]['id']
            r = client.get(f'/api/authors/{dynasty_id}')
            print(f'\nAuthors of {dynasty_id}:', r.status_code)
            if r.status_code == 200:
                authors = json.loads(r.data)
                print(f'Total: {len(authors)}')
                for a in authors[:3]:
                    print(f'  - {a}')
            
            # 测试诗词接口
            if authors:
                author_id = authors[0]['id']
                r = client.get(f'/api/poems/{author_id}')
                print(f'\nPoems of {author_id}:', r.status_code)
                if r.status_code == 200:
                    poems = json.loads(r.data)
                    print(f'Total: {len(poems)}')
                    for p in poems[:3]:
                        print(f'  - {p}')
                    
                    # 测试诗词详情
                    if poems:
                        poem_id = poems[0]['poem_id']
                        r = client.get(f'/api/poem/{poem_id}')
                        print(f'\nPoem detail {poem_id}:', r.status_code)
                        if r.status_code == 200:
                            data = json.loads(r.data)
                            print(f"Title: {data['poem']['title']}")
                            print(f"Author: {data['poem']['author']}")
                            print(f"Content preview: {data['poem']['content'][:50] if data['poem']['content'] else 'N/A'}...")

print('\nOK - API tests completed!')
