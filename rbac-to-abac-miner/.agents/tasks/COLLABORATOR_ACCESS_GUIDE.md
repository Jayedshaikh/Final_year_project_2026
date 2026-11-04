# How to Add Collaborator Access - GitHub Repository

## 📋 For Jayed (Repository Owner)

### Step-by-Step Guide to Add Naeem as Collaborator

---

## Method 1: Via GitHub Website (Easiest) 🌐

### Step 1: Go to Repository Settings
1. Open browser and go to:
   ```
   https://github.com/Jayedshaikh/Final_year_project_2026
   ```

2. Click on **"Settings"** tab (top right, near Code/Issues/Pull requests)

### Step 2: Navigate to Collaborators
1. In left sidebar, click **"Collaborators and teams"**
   - Or directly go to:
   ```
   https://github.com/Jayedshaikh/Final_year_project_2026/settings/access
   ```

2. GitHub may ask for password confirmation (security)

### Step 3: Add Collaborator
1. Click **"Add people"** button (green button)

2. In the search box, enter Naeem's GitHub username
   - Search by: GitHub username, email, or full name

3. Select correct user from dropdown

### Step 4: Choose Permission Level
Select permission level:
- ✅ **"Write"** - Recommended for team members
  - Can push to branches
  - Can create PRs
  - Can review code
  - Can merge (if branch protection allows)

- **"Maintain"** - More permissions
  - All Write permissions +
  - Can manage settings

- **"Admin"** - Full control (not needed for regular team member)

**Recommendation:** Select **"Write"** for Naeem

### Step 5: Send Invitation
1. Click **"Add [username] to this repository"**

2. GitHub will send invitation email to Naeem

3. Naeem will receive notification

---

## Method 2: Via Command Line (GitHub CLI) 💻

If Jayed has GitHub CLI installed:

```bash
# Add collaborator with write permission
gh api repos/Jayedshaikh/Final_year_project_2026/collaborators/NAEEM_USERNAME -X PUT -f permission=push

# Replace NAEEM_USERNAME with Naeem's actual GitHub username
```

---

## 📧 What Naeem Will Receive

### Email Notification:
```
Subject: Invitation to collaborate on Jayedshaikh/Final_year_project_2026

Jayed has invited you to collaborate on the repository 
Jayedshaikh/Final_year_project_2026.

[View invitation]
```

### Naeem's Steps:
1. Check email
2. Click "View invitation" link
3. Or go to: https://github.com/Jayedshaikh/Final_year_project_2026/invitations
4. Click **"Accept invitation"**
5. Done! Now can create PRs

---

## ✅ Verification (After Naeem Accepts)

### Check if Added Successfully:
1. Go to repository Settings → Collaborators
2. Naeem should appear in collaborators list
3. Status should show "Active" (green checkmark)

---

## 🎯 Quick Links for Jayed:

**Direct Settings Link:**
```
https://github.com/Jayedshaikh/Final_year_project_2026/settings/access
```

**After Adding:**
- Naeem can create Pull Requests ✅
- Naeem can push to branches ✅
- Naeem can review code ✅

---

## 📱 Alternative: Add via GitHub Mobile App

If Jayed is on mobile:

1. Open GitHub app
2. Go to repository
3. Tap "..." (three dots)
4. Tap "Settings"
5. Tap "Manage access"
6. Tap "Invite a collaborator"
7. Enter Naeem's username
8. Select "Write" permission
9. Send invitation

---

## ⚠️ Common Issues & Solutions

### Issue 1: "Add people" button is grayed out
**Solution:** 
- Confirm you're the repository owner
- Check if you're logged in correctly
- Try refreshing the page

### Issue 2: Can't find Naeem's username
**Solution:**
- Ask Naeem for exact GitHub username (case-sensitive)
- Or use email address instead
- Check spelling carefully

### Issue 3: Invitation not received
**Solution:**
- Check spam folder
- Verify email address in GitHub settings
- Resend invitation from Settings → Collaborators

---

## 🔒 Recommended: Set Branch Protection (Optional but Good Practice)

After adding collaborators, protect main/develop branches:

1. Go to Settings → Branches
2. Add rule for "develop" branch
3. Enable:
   - ✅ Require pull request reviews before merging
   - ✅ Require status checks to pass (if CI setup)
   - ✅ Require branches to be up to date

This ensures all changes go through PR review process.

---

## 👥 Full Team Setup (Recommended)

Add all 4 team members as collaborators:

1. **Naeem** (Frontend) - Write access
2. **Shweta** (Data/QA) - Write access  
3. **Granthali** (Policy Engine) - Write access
4. **Jayed** (Backend Lead) - Admin (already owner)

**Why:** 
- Everyone can create PRs
- Proper code review workflow
- Team collaboration enabled

---

## ✅ After Access Granted:

Naeem can then:
1. Create Pull Request from `feature/naeem-frontend`
2. Request reviews from team
3. Merge after approval

---

## 📞 Need Help?

If Jayed faces any issue:
1. Check GitHub documentation: https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-personal-account-on-github/managing-access-to-your-personal-repositories/inviting-collaborators-to-a-personal-repository
2. Contact GitHub support
3. Ask team for help

---

**Time Required:** 2-3 minutes  
**Difficulty:** Easy  
**Required:** Repository owner/admin access

