
#!/usr/bin/env fish
git checkout --orphan latest_branch
git add -A
git commit -am "Initial Commit"
git branch -D main
git branch -m main
git push -f origin main
git push --set-upstream origin main
git push