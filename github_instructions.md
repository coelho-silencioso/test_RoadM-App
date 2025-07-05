# GitHub Instructions for test_RoadM-App

This document provides detailed instructions for committing and pushing your test_RoadM-App code to GitHub. There are two options available: using the application's built-in GitHub functionality or using Git commands directly.

## Prerequisites

Before you begin, make sure you have:
1. A GitHub account (create one at https://github.com/join if needed)
2. Git installed on your computer (download from https://git-scm.com/downloads if needed)

## OPTION 1: Using the application's built-in GitHub functionality (Recommended)

This is the easiest method as it handles all Git operations through the application's user interface.

### Step 1: Create a new repository on GitHub
1. Go to https://github.com/new
2. Name it 'test_RoadM-App'
3. Make it public or private as you prefer
4. Do NOT initialize with README, .gitignore, or license
5. Click 'Create repository'
6. Note the repository URL (it should look like `https://github.com/yourusername/test_RoadM-App.git`)

### Step 2: Configure the repository in the application
1. Launch the application by running `python main.py`
2. Go to File menu > GitHub > Configure Repository
3. The dialog will be pre-filled with 'https://github.com/coelho-silencioso/test_RoadM-App.git'
4. Replace it with your own repository URL from Step 1
5. Click OK to confirm

### Step 3: Commit and push your changes
1. Go to File menu > GitHub > Commit and Push
2. Enter a descriptive commit message (e.g., 'Initial commit' or 'Update roadmap structure')
3. Click OK to push your code to GitHub
4. A success message will appear if the push was successful

### Troubleshooting
- If you get a "Git Not Found" error, make sure Git is installed and added to your system PATH
- If you get a "Git Repository Not Found" error, click "Yes" to configure the repository
- If you get a "Push Failed" error, check the error message for details:
  - Authentication issues: Make sure you have the correct permissions for the repository
  - Branch issues: The application will automatically try both 'master' and 'main' branches

## OPTION 2: Using Git commands directly

If you prefer using Git from the command line, follow these steps:

### Step 1: Create a new repository on GitHub
1. Go to https://github.com/new
2. Name it 'test_RoadM-App'
3. Make it public or private as you prefer
4. Do NOT initialize with README, .gitignore, or license
5. Click 'Create repository'

### Step 2: Initialize a Git repository (if not already done)
1. Open a terminal/command prompt
2. Navigate to your test_RoadM-App directory:
   ```
   cd path\to\your\test_RoadM-App
   ```
3. Initialize a Git repository:
   ```
   git init
   ```

### Step 3: Configure the remote repository
1. Add your GitHub repository as the remote origin:
   ```
   git remote add origin https://github.com/yourusername/test_RoadM-App.git
   ```
   (Replace 'yourusername' with your actual GitHub username)

### Step 4: Commit your changes
1. Add all files to the staging area:
   ```
   git add .
   ```
2. Commit the changes with a descriptive message:
   ```
   git commit -m "Initial commit"
   ```

### Step 5: Push your code to GitHub
1. Push your code to the remote repository:
   ```
   git push -u origin master
   ```
2. If your default branch is 'main' instead of 'master', use:
   ```
   git push -u origin main
   ```

### Troubleshooting
- If you're asked for credentials, enter your GitHub username and password or personal access token
- If you get a "fatal: remote origin already exists" error, use:
  ```
  git remote set-url origin https://github.com/yourusername/test_RoadM-App.git
  ```
- If you're not sure which branch you're on, use:
  ```
  git branch
  ```

## Verifying Your Code on GitHub

After completing either option, you can verify your code is on GitHub by visiting:
```
https://github.com/yourusername/test_RoadM-App
```
(Replace 'yourusername' with your actual GitHub username)

## Additional Notes

- The application automatically adds all files to the staging area before committing
- The application tries both 'master' and 'main' branch names when pushing
- If you make changes to your code, you can push them again using the same process
- You can view your commit history on GitHub by clicking on the "Commits" tab in your repository
- This repository contains a roadmap application that allows you to create and organize nodes with connections
- The application includes built-in GitHub functionality to make it easy to save your work to the cloud