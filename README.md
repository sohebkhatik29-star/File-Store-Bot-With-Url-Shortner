# 🎬 ASH AUTOMATIC MOVIE FILE STORE BOT 🎬

Ek modern, fully automatic aur professional Telegram Movie File Store Bot with **Active Movie Sessions**, **Multiple Quality Grouping**, **Automatic Poster Extraction**, aur **Netflix-Style "ASH MOVIES" Cards**.

---

## 🌟 Key Features

1. **Automatic Movie Indexing**:
   - Movie file/video bhejte hi title, year, audio languages aur quality (480p, 720p, 1080p, 4K) automatically extract ho jati hai.
   - Unique short Movie ID aur permanent shareable Telegram deep link generate hota hai.

2. **Active Movie Session System (Strict Protection)**:
   - Admin sabse pehle movie ki pehli file upload karta hai (jaise `RRR 480p`).
   - Bot active session `RRR` set kar leta hai.
   - Agli files `RRR 720p`, `RRR 1080p`, `RRR 2160p` ek hi movie record ke andar save hoti hain.
   - Agar galti se koi alag movie (jaise `KGF 720p`) bheji jaye, to bot **strict mismatch warning** deta hai aur KGF ko RRR mein merge nahi karta!
   - Session MongoDB mein persist rehta hai, yani bot restart hone par bhi active session restore ho jata hai.

3. **Movie Quality Grouping**:
   - Single clean document per movie jisme qualities ka mapping hota hai: `480p`, `720p`, `1080p`, `2160p`.
   - Duplicate quality upload hone par confirmation alert: `[Replace Quality]` / `[Keep Existing]`.

4. **Automatic Video Poster Extraction**:
   - Video ke embedded thumbnail ko extract karke movie card ka verified poster banata hai.
   - Ek movie ki sabhi qualities ek hi verified poster share karti hain.
   - Manual poster upload karne ka option (`photo` bhejkar ya `/setposter`).

5. **Netflix-Inspired "ASH MOVIES" Cards**:
   - Clean, modern layout with Title, Year, Audio chips, and clickable quality buttons with file sizes.
   - User button par click karte hi direct file receive karta hai with 30-minute auto-delete warning for copyright protection.

6. **Shareable Link System with URL Shortener Fallback**:
   - Format: `https://t.me/<BOT_USERNAME>?start=mov_<movie_id>`
   - Agar URL Shortener enabled ho to short link deta hai. Agar shortener API fail ho jaye to direct Telegram link fallback provide karta hai.

---

## 📋 Bot Commands (Admin Only)

| Command | Description |
|---|---|
| `/start` | Bot welcome menu ya deep link se movie open karna |
| `/newmovie <Title>` | Explicit nayi movie session shuru karna |
| `/finish` | Current movie session complete karna aur finalized card & link lena |
| `/cancel` | Current active session ko cancel karna |
| `/status` | Active movie aur uski saved qualities ka real-time status dekhna |
| `/movies` | Stored movie library list dekhna with pagination |
| `/delete <movie_id>` | Kisi movie ko database se remove karna |
| `/stats` | Total users, movies aur system statistics check karna |
| `/broadcast` | Sabhi users ko message broadcast karna |

---

## ⚙️ Environment Variables (Render / VPS)

| Variable | Description | Example |
|---|---|---|
| `API_ID` | Telegram API ID from my.telegram.org | `1234567` |
| `API_HASH` | Telegram API Hash from my.telegram.org | `0123456789abcdef` |
| `BOT_TOKEN` | Bot Token from @BotFather | `7123456789:AAH...` |
| `BOT_USERNAME` | Bot username without @ | `AshMovieStoreBot` |
| `BOT_OWNER` | Owner Telegram User ID | `987654321` |
| `ADMINS` | Optional extra admin IDs separated by space | `987654321 11223344` |
| `DB_CHANNEL` | Telegram Private Channel ID with -100 | `-1001234567890` |
| `DATABASE_URL` | MongoDB Atlas Connection URI | `mongodb+srv://user:pass@cluster...` |
| `DATABASE_NAME` | MongoDB database name | `AshMovieBot` |
| `LOG_CHANNEL` | Channel ID for floodwait & error logs | `-1001234567890` |
| `UPDATES_CHANNEL` | Optional channel username or ID for force sub | `AshMoviesUpdates` |
| `SHORTLINK_URL` | Optional shortener domain (e.g. shareus.io) | `shareus.io` |
| `SHORTLINK_API` | Optional shortener API key | `abcdef123456` |
| `AUTO_DELETE_TIME` | File auto delete duration in seconds (default 1800) | `1800` |

---

## 📱 Android Mobile Se GitHub Par Deploy Karne Ke Steps

1. Chrome browser mein [GitHub.com](https://github.com) kholein aur login karein.
2. Apni repository `File-Store-Bot-With-Url-Shortner` par jayein.
3. **Desktop Site Mode** on karein (Chrome ke 3 dots menu par tap karke "Desktop site" tick karein).
4. `configs.py`, `bot.py`, `requirements.txt`, `Dockerfile`, `render.yaml` ko edit karein (Pencil icon ✏️ par tap karke code replace karein aur neeche "Commit changes" par tap karein).
5. `handlers/` folder ke andar nayi files add karne ke liye **Add file > Create new file** par tap karein:
   - Type `handlers/parser.py` -> paste code -> Commit.
   - Type `handlers/poster.py` -> paste code -> Commit.
   - Type `handlers/session_manager.py` -> paste code -> Commit.
   - Type `handlers/movie_card.py` -> paste code -> Commit.
   - `handlers/database.py`, `handlers/save_media.py`, `handlers/send_file.py` ko update karein.
6. Render dashboard ([render.com](https://render.com)) par login karein:
   - Apni Web Service par jayein.
   - "Environment" tab mein jaakar upar diye gaye Environment Variables save karein.
   - "Manual Deploy > Deploy latest commit" par tap karein!
