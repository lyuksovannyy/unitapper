# unitapper
Open-Source script with easy telegram account handling and using it for telegram crypto clicker bots

# Features
- Asynchronous
- Multi account support
- Proxy support
- Simple webpanel with all needed information about your accounts and ability to change config file for every one
- Easy to develop your own script for any clicker (ofc if you have basic knowing about requests and how to work with them)

# Short overview
All scripts are written by me and most are outdated and won't work at all
If you gonna proceed with installation, you doing it at your own risk! And no assistance are gonna be provided, aswell updates.

# Download & Install
Installation is very easy, all you need is:
- Python 3.11
- Download this project

# Preparing
- Unarchive this project to any directory you want and open it.
- Open console inside the folder (in search bar write: `cmd`).
- Write in cmd `pip install -r requirements.txt` it will install all mandatory dependencies for you.
- Rename `.env.example` to `.env` and adjust settings for your needs (API_ID, API_HASH are mandatory to add new accounts).
- After installation completed, write `python3 __main__.py`

# Setup
## Adding account
- At fist start when you have no accounts, you'll prompted to add you account to script, follow instructions that script says to add account.
- After successfully adding account to script you can start it, it will prepare all sessions for clickers and will work asynchronously.
## Proxies
- You can add proxies for your accounts to avoid ban for multiple-accounts in clicker games.
- Reffer to proxies.txt file to learn more (simple to setup)
## Startup parameters
- `-option X` - Select an option without user's input, ex.: `python __main__.py -option 1` this one gonna start farming immediately after running command.
- `-script script1.py,script2.py` - for developers, Start only selected scripts, you can use coma( , ) to select multiple scripts.
- `-session session_name1,session_name2` - for developers, Start only selected sessions, you can use coma( , ) to select multiple sessions.
