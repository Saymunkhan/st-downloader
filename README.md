# ST DOWNLOADER - Termux/PC chhara (shudhu phone, online host)

App-ta ekta free online server-e chalate hobe. Tarpor phone-er Chrome-e link khule
"Add to Home screen" dile ST DOWNLOADER nam o icon shoho app-er moto thakbe.

## Step 1: GitHub-e file upload
1. github.com-e free account kholun, notun repository banan (nam: st-downloader).
2. "Add file" > "Upload files" diye ei 3-ta file upload korun: `app.py`, `requirements.txt`, `README.md`
3. "Commit changes" chapun.

## Step 2: Render-e host (free)
1. render.com-e GitHub diye sign up korun.
2. New > Web Service > apnar st-downloader repo select korun.
3. Settings:
   - Runtime: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --timeout 300`
   - Instance type: Free
4. Environment Variables-e add korun:
   - `ADMIN_PASSWORD` = apnar nijer password
   - `SECRET_KEY` = jekono lomba random lekha
5. Create Web Service chapun. Kichhukkhon por ekta link pabn (https://st-downloader-xxxx.onrender.com).

## Step 3: Phone-e app hishebe rakha
Chrome-e oi link kholun > 3-dot menu > **Add to Home screen / Install app**.
Admin panel: `apnar-link/admin`

## Shimabodhota (sotti kotha)
- Free server 15 minute kaj na korle ghumiye jay; prothom khulte ~1 minute lagte pare.
- YouTube onekshomoy cloud server-er IP block kore ("Sign in to confirm you're not a bot").
  Tai YouTube kaj na-o korte pare. Facebook ar TikTok shadharonoto kaj kore.
- Free server-e ffmpeg thake na, tai "Best quality" ar "MP3" kaj korbe na. Normal download kaj korbe.
- Kaj bondho hole requirements.txt-e `yt-dlp` thakle Render-e "Manual Deploy > Clear build cache & deploy" korun, tahole latest yt-dlp ashe.
- Nijer bhishon bhalo hole link kaurke dibenna, karon tar server-er bandwidth apnar.
- Shudhu nijer video ba jeta download korar anumoti ache setar jonno use korun.
