# Put Asset Register online

Use Vercel for the website and Render for the server and database. No other host is needed.

## 1. Put the code in your Git account

1. Create a private GitHub repository called `asset-register`.
2. In this folder, run `git remote add origin YOUR_REPOSITORY_ADDRESS`, then `git push -u origin master`.
3. Do not upload `.env`, `.local`, `.venv` or `node_modules`. The supplied ignore file excludes them.

## 2. Create the Render database and server

1. Sign in at [Render](https://dashboard.render.com/).
2. Choose **New → Blueprint**.
3. Connect the GitHub account and select the repository from step 1.
4. Select the branch containing this code. Render reads `render.yaml` and proposes one database and one server.
5. Review the plans. The supplied file uses the free plans. Choose suitable paid plans for judging if you want to avoid free-service sleep and database expiry. Check the current terms before paying.
6. Set `DEMO_PASSWORD` to a fresh, random password of 10–72 bytes. Keep it in your password manager, not in Git. The same password seeds the four demo accounts.
7. Set `ALLOWED_ORIGINS` to the Vercel website's origin when it is available. For the first server build, use `http://localhost:5173`.
8. Render generates `SECRET_KEY` and fills `DATABASE_URL` from the database. Do not replace the database address with a Vercel address.
9. Choose **Apply**. The Docker image installs the server packages, creates the tables, seeds the full catalog, and loads the sample demo through imports and approvals because `LOAD_SAMPLE_DATA=true`.
10. Open the server service, copy its actual address, and visit its `/health` path. Expect `{"ok":true}`. If setup fails, inspect **Logs**; do not continue with a broken server.
11. The database's external access list is empty. The server uses Render's internal database connection.

`SHOW_DEMO_SIGN_INS=true` displays the environment-supplied demo password after a role is selected, as requested for this hiring demo. This is deliberately a sample-only deployment. Set it to `false` before adding real records. Changing `DEMO_PASSWORD` later does not silently reset existing users' password hashes.

## 3. Create or connect the Vercel website

The website already exists at **https://asset-register-pravi.vercel.app**. Once Render is ready, use steps 5 and 8 below to set `VITE_API_URL` and redeploy. The other steps describe recreating it if needed.

1. Sign in at [Vercel](https://vercel.com/dashboard).
2. Choose **Add New → Project** and import the same repository.
3. Set **Root Directory** to `web` and choose the Vite preset.
4. Set **Build Command** to `npm run build` and **Output Directory** to `dist`.
5. Add `VITE_API_URL` with the actual Render server origin, without a trailing slash. This value is public; it is not a secret.
6. Choose **Deploy**. Copy the actual website origin.
7. In Render, open **Environment**, replace `ALLOWED_ORIGINS` with that origin, and choose **Save, rebuild, and deploy**.
8. If the website was already deployed from the CLI, add `VITE_API_URL` under **Project → Settings → Environment Variables**, then redeploy the latest production deployment. Vite reads this setting at build time.

CLI alternative from `web/`: run `npx vercel env add VITE_API_URL production`, enter the Render origin, then run `npx vercel --prod`.

## 4. Check the connected deployment

1. Open the Vercel address. Select Viewer and sign in with the displayed sample credentials.
2. Open Map, Assets, an asset, Contracts, Problems, Reports and How it works. Refresh a nested asset page; it must still open.
3. Sign in as Editor. Upload `server/db/seed/samples/roads_second_version.csv` into the Roads Department road list. Expect 5 new, 8 changed and 2 missing.
4. Sign in as Reviewer. Approve one addition and reject one update with a reason. Confirm history on the affected asset.
5. Sign in as Editor and import `lights_second.csv` into the Ward electrical list. As Reviewer, inspect a possible match before linking.
6. Review the waiting warranty request, choose Bad workmanship, and open the draft letter. The register does not send it.
7. Record the real addresses and the result of each check in `docs/HANDOVER.md`.

These settings follow the [Render Blueprint reference](https://render.com/docs/blueprint-spec) and [Vercel's Vite deployment guide](https://vercel.com/docs/frameworks/frontend/vite), checked during this build. Account access and successful live checks are still required before calling the whole app deployed.
