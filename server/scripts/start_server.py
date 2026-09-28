import os
import uvicorn

if os.getenv('LOAD_SAMPLE_DATA','false').lower()=='true':
    from scripts.load_demo_state import load_demo
    load_demo()
uvicorn.run('app.main:app',host='0.0.0.0',port=int(os.getenv('PORT','8000')))
