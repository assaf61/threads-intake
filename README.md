# threads-intake — לכידת חוטים

PWA אישי ללכידה בשניות של רעיון / הקלטה / תמונה / לינק / טקסט אל
`Alma Mind/Alma.Threads/00-raw/inbox/` ב-OneDrive, מהטלפון (Android) ומהמחשב.

## ארכיטקטורה

- **קליינט בלבד, ללא build step.** vanilla ES modules + MSAL.js מ-CDN.
- **Auth:** Entra SPA (single tenant alma01.com), PKCE, הרשאות delegated `Files.ReadWrite` + `User.Read`.
- **כתיבה:** Microsoft Graph `PUT /me/drive/root:/.../content` (conflictBehavior=rename); uploadSession לקבצים גדולים.
- **Offline-first:** כל לכידה נכתבת ל-IndexedDB קודם, מסונכרנת ברקע. לכידה לא נכשלת לעולם.
- **העשרה:** `worker/enrich.py` רץ במחשב (Scheduled Task), מתמלל קול בעברית ומציע vault. ראו worker/.

## קבצים

| קובץ | תפקיד |
|------|-------|
| `config.js` | clientId, authority, נתיב inbox |
| `note.js` | בניית קובץ .md תקני (frontmatter לפי חוקי הוולט) |
| `queue.js` | תור IndexedDB (לכידות, שיתופים נכנסים, kv) |
| `auth.js` | עטיפת MSAL |
| `graph.js` | העלאות Graph (PUT קטן + uploadSession) |
| `app.js` | ממשק: 4 כפתורים, edit-sheet, ניקוז תור |
| `sw.js` | cache של ה-shell + קליטת share_target |

## הרצה מקומית

```
serve-local.cmd   →  http://localhost:8848/
```

## פריסה

git push ל-GitHub (repo ציבורי) עם Pages פעיל. אין סודות בקוד —
clientId של SPA הוא ציבורי by design, וה-tenant חסום למשתמשים חיצוניים.

## חוקי ברזל (מהוולט)

- שמות קבצים: אנגלית kebab-case בלבד.
- `target_vault: alma-threads` קבוע — ההעשרה מציעה (`suggested_vault`), לא מחליטה.
- טקסט משתמש רק בגוף ההערה, לעולם לא ב-frontmatter.
