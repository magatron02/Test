---
description: Save and push all changes to GitHub (sync between computers)
---

Run these commands to sync everything to GitHub:

```bash
cd "C:\Users\VRTWINS_Creative\Desktop\AI_Create"
git add -A
git commit -m "quicksave: sync $(date '+%Y-%m-%d %H:%M')" --allow-empty
git push origin main
```

After running, confirm with the push result. If there are merge conflicts or the push is rejected (because the other computer pushed first), run `git pull --rebase origin main` first, then push again.
