"""Make private local settings without overwriting existing files."""
from pathlib import Path
import secrets
root=Path(__file__).resolve().parents[2]
paths=[root/'.env',root/'server/.env',root/'web/.env']
if any(p.exists() for p in paths):
    raise SystemExit('Local settings already exist. Keep them or move them aside first.')
password=secrets.token_urlsafe(24)
paths[0].write_text('DATABASE_PASSWORD='+password+'\n')
paths[1].write_text('\n'.join(['DATABASE_URL=postgresql://asset_register:'+password+'@localhost:5432/asset_register','SECRET_KEY='+secrets.token_urlsafe(40),'DEMO_PASSWORD='+secrets.token_urlsafe(18),'ALLOWED_ORIGINS=http://localhost:5173','SHOW_DEMO_SIGN_INS=true','LOAD_SAMPLE_DATA=true','PHOTO_STORAGE=database','TIME_ZONE=Asia/Kolkata','']))
paths[2].write_text('VITE_API_URL=http://localhost:8000\n')
print('Private settings created. Select a role on the local sign-in page to see its demo credentials.')
