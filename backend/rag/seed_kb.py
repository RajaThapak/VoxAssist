SEED_KB_ARTICLES = [
    {
        "id": "kb_vpn_01",
        "title": "VPN keeps disconnecting or fails authentication",
        "category": "Network",
        "keywords": ["vpn", "disconnect", "connect", "authentication", "network", "tunnel"],
        "steps": [
            "Open GlobalProtect / Cisco AnyConnect VPN client.",
            "Disconnect the current session and quit the client completely.",
            "Flush DNS cache by opening Terminal / Command Prompt and running 'ipconfig /flushdns'.",
            "Reconnect to server 'vpn.company.com' using your corporate username and MFA approval."
        ]
    },
    {
        "id": "kb_wifi_01",
        "title": "Wi-Fi drops repeatedly or weak signal troubleshooting",
        "category": "Network",
        "keywords": ["wifi", "wi-fi", "wireless", "internet", "signal", "drop", "disconnect"],
        "steps": [
            "Turn off Wi-Fi adapter, wait 5 seconds, and turn it back on.",
            "Forget the corporate Wi-Fi network 'Corp-Secure' and re-select it from available networks.",
            "Ensure you are within range of access points and not on a 2.4GHz Guest frequency.",
            "Restart your wireless network adapter in Device Manager / Network Connections."
        ]
    },
    {
        "id": "kb_pwd_01",
        "title": "Corporate Password Reset and Expiration Flow",
        "category": "Account",
        "keywords": ["password", "reset", "forgot", "expired", "active directory", "account lock"],
        "steps": [
            "Navigate to https://identity.company.com/reset on a mobile or secondary device.",
            "Verify your identity via Okta / Duo MFA push notification.",
            "Create a new password that is at least 14 characters with uppercase, lowercase, numbers, and symbols.",
            "Wait 2 minutes for Active Directory sync across laptop local credentials."
        ]
    },
    {
        "id": "kb_mfa_01",
        "title": "MFA Lockout and Authenticator Device Recovery",
        "category": "Account",
        "keywords": ["mfa", "2fa", "okta", "duo", "authenticator", "locked out", "phone change"],
        "steps": [
            "Ensure airplane mode is off and your mobile phone has data/Wi-Fi connection.",
            "If you received a new phone, select 'Use Backup Verification Code' on login screen.",
            "If locked out after 5 failed attempts, wait 15 minutes for automatic lockout expiration.",
            "Contact IT helpdesk to issue a temporary 8-digit bypass passcode."
        ]
    },
    {
        "id": "kb_print_01",
        "title": "Printer offline, missing driver, or stuck print queue",
        "category": "Hardware",
        "keywords": ["printer", "print", "offline", "spooler", "stuck queue", "paper jam"],
        "steps": [
            "Open Services (services.msc) and restart the 'Print Spooler' service.",
            "Check if printer IP address '192.168.10.50' is pingable from Command Prompt.",
            "Remove the printer from Settings -> Printers & Scanners and click 'Add Printer' to auto-discover.",
            "Clear pending print jobs from C:\\Windows\\System32\\spool\\PRINTERS."
        ]
    },
    {
        "id": "kb_disk_01",
        "title": "Low disk space warning and storage cleanup",
        "category": "System",
        "keywords": ["disk space", "storage", "c drive", "clean up", "full disk", "temp files"],
        "steps": [
            "Run Disk Cleanup (cleanmgr.exe) as Administrator and purge System Temp files.",
            "Empty the Recycle Bin and Downloads folder.",
            "Clear Outlook attachments cache and Teams local cache (%appdata%\\Microsoft\\Teams\\Cache).",
            "Verify C: drive has at least 15 GB of free space."
        ]
    },
    {
        "id": "kb_outlook_01",
        "title": "Outlook email sync issues or stuck in offline mode",
        "category": "Software",
        "keywords": ["outlook", "email", "sync", "offline", "ost file", "mailbox"],
        "steps": [
            "Check the status bar in Outlook to confirm if it says 'Disconnected' or 'Trying to Connect'.",
            "Go to Send / Receive tab and toggle 'Work Offline' to reconnect.",
            "Run Outlook in Safe Mode (outlook.exe /safe) to check for corrupt add-ins.",
            "Rebuild the Outlook OST data file if emails fail to sync after 30 minutes."
        ]
    },
    {
        "id": "kb_teams_01",
        "title": "Microsoft Teams microphone or webcam not detected",
        "category": "Software",
        "keywords": ["teams", "mic", "microphone", "webcam", "camera", "audio", "video"],
        "steps": [
            "Open Windows Settings -> Privacy & Security -> Microphone/Camera and enable App Permissions.",
            "In Teams Settings -> Devices, verify the correct Microphone and Speaker hardware are selected.",
            "Test audio with 'Make a test call' in Teams Device Settings.",
            "Restart Microsoft Teams from Task Manager."
        ]
    },
    {
        "id": "kb_vdi_01",
        "title": "VDI and Remote Desktop connection failure",
        "category": "System",
        "keywords": ["vdi", "citrix", "horizon", "rdp", "remote desktop", "virtual desktop"],
        "steps": [
            "Ensure you are connected to the corporate VPN before launching Citrix / VMware Horizon.",
            "Clear browser cache or launch the VDI client directly rather than via web portal.",
            "Restart the Workspace / Horizon Client process in Task Manager.",
            "Check if your virtual machine status is Active on the IT VDI dashboard."
        ]
    },
    {
        "id": "kb_perf_01",
        "title": "Slow laptop performance or high CPU/RAM usage",
        "category": "System",
        "keywords": ["slow", "lag", "cpu", "ram", "memory", "task manager", "freezing"],
        "steps": [
            "Open Task Manager (Ctrl + Shift + Esc) and check which process is consuming high CPU/Memory.",
            "Close memory-heavy browser tabs or restart Google Chrome / Edge.",
            "Check for pending Windows Updates and reboot the machine.",
            "Ensure at least 10% of total RAM is available."
        ]
    },
    {
        "id": "kb_git_01",
        "title": "Git SSH Key Permission Denied and Agent Setup",
        "category": "Developer Tools",
        "keywords": ["git", "github", "gitlab", "ssh", "permission denied", "publickey", "id_rsa", "ssh-add"],
        "steps": [
            "Verify SSH agent is running in terminal by calling 'eval $(ssh-agent -s)'.",
            "Add your private key to SSH agent via 'ssh-add ~/.ssh/id_ed25519' or 'ssh-add ~/.ssh/id_rsa'.",
            "Copy public key 'cat ~/.ssh/id_ed25519.pub' and add it under GitHub/GitLab SSH Settings.",
            "Test connection by running 'ssh -T git@github.com'."
        ]
    },
    {
        "id": "kb_docker_01",
        "title": "Docker Daemon Socket Failure and Port Binding Errors",
        "category": "Cloud & DevOps",
        "keywords": ["docker", "container", "socket", "daemon", "port", "port in use", "docker.sock"],
        "steps": [
            "Verify Docker Desktop service status and restart it from the system tray menu.",
            "If 'bind: address already in use' occurs, find process via 'netstat -ano | grep <port>' and kill process ID.",
            "On Linux/macOS, ensure user belongs to docker group via 'sudo usermod -aG docker $USER'.",
            "Reset Docker daemon to factory defaults via Docker Desktop Troubleshoot menu if daemon hangs."
        ]
    },
    {
        "id": "kb_env_01",
        "title": "Node.js and Python Virtual Environment Path Misconfiguration",
        "category": "Developer Tools",
        "keywords": ["node", "npm", "python", "pip", "venv", "path", "command not found", "virtualenv"],
        "steps": [
            "Verify Python virtual environment is activated ('source venv/bin/activate' or '.\\venv\\Scripts\\Activate.ps1').",
            "Confirm active executable path using 'which python' / 'where.exe python' and 'which npm'.",
            "Clear npm cache using 'npm cache clean --force' and delete node_modules before 'npm install'.",
            "Update PATH environment variable in System Settings to point to installed runtime binaries."
        ]
    },
    {
        "id": "kb_sec_01",
        "title": "BitLocker and FileVault Disk Encryption Recovery Prompt",
        "category": "Security",
        "keywords": ["bitlocker", "filevault", "encryption", "recovery key", "tpm", "disk lock", "boot"],
        "steps": [
            "Retrieve 48-digit BitLocker recovery key from Microsoft Azure AD Portal or company IT self-serve portal.",
            "On macOS FileVault, retrieve recovery key from company MDM (Jamf) console.",
            "Type recovery key carefully into blue boot prompt screen.",
            "If prompt recurs on every reboot, suspend BitLocker in Windows and re-enable after BIOS update."
        ]
    },
    {
        "id": "kb_edr_01",
        "title": "SentinelOne and CrowdStrike EDR False Positive Quarantine",
        "category": "Security",
        "keywords": ["sentinelone", "crowdstrike", "edr", "quarantine", "antivirus", "false positive", "blocked"],
        "steps": [
            "Check the desktop EDR tray icon notification to identify the quarantined executable path.",
            "Do NOT attempt to manually rename or bypass security agent files.",
            "Verify file checksum against corporate approved software directory.",
            "Submit an IT Security exclusion request ticket with file path and hash for analyst release."
        ]
    },
    {
        "id": "kb_cloud_01",
        "title": "AWS and Azure CLI SSO Credentials Expiration Flow",
        "category": "Cloud",
        "keywords": ["aws", "azure", "cloud", "cli", "sso", "credentials", "expired", "token", "kubectl"],
        "steps": [
            "Run 'aws sso login --profile <profile-name>' or 'az login --use-device-code' in terminal.",
            "Complete browser MFA challenge prompt.",
            "Verify credentials by calling 'aws sts get-caller-identity' or 'az account show'.",
            "Refresh your local kubeconfig via 'aws eks update-kubeconfig' if accessing Kubernetes clusters."
        ]
    },
    {
        "id": "kb_saas_01",
        "title": "Slack, Jira, and Confluence SSO Redirect Loop and Permissions",
        "category": "SaaS",
        "keywords": ["slack", "jira", "confluence", "sso", "redirect loop", "atlassian", "permissions"],
        "steps": [
            "Clear site cookies for *.atlassian.net and *.slack.com in browser settings.",
            "Sign out of all secondary Google/Okta accounts in the browser.",
            "Open an Incognito / Private window and log in through your corporate SSO portal.",
            "If workspace permissions error shows, request role assignment via IT Access Portal."
        ]
    },
    {
        "id": "kb_dock_01",
        "title": "USB-C Dock and DisplayLink External Monitor Resolution Failure",
        "category": "Hardware",
        "keywords": ["dock", "docking", "usb-c", "displaylink", "monitor", "resolution", "display", "dual monitor"],
        "steps": [
            "Unplug power cord from the USB-C dock, wait 10 seconds, and plug power back in.",
            "Ensure laptop Thunderbolt / USB-C port supports DisplayPort Alt Mode.",
            "Update DisplayLink Manager app to latest version on macOS/Windows.",
            "Press Win + P (or macOS Displays settings) and select 'Extend' desktop."
        ]
    },
    {
        "id": "kb_audio_01",
        "title": "Bluetooth Headset Pairing Failure and Input Mute Lock",
        "category": "Hardware",
        "keywords": ["bluetooth", "headset", "headphones", "pairing", "mic mute", "audio", "airpods"],
        "steps": [
            "Remove headset from Windows/macOS Bluetooth device list ('Forget Device').",
            "Hold power/pairing button on headset for 7 seconds until LED blinks pairing mode.",
            "Re-pair headset in Bluetooth settings and set as Default Communication Device.",
            "Unmute hardware physical switch on headset boom mic."
        ]
    },
    {
        "id": "kb_phish_01",
        "title": "Suspicious Email Reporting and Phishing Attachment Isolation",
        "category": "Security",
        "keywords": ["phishing", "suspicious", "spam", "email", "attachment", "malware", "report"],
        "steps": [
            "Do NOT click any links, open attachments, or reply to the email.",
            "Click the 'Report Phishing' button in Outlook ribbon or web toolbar.",
            "If an attachment was accidentally opened, immediately disconnect Wi-Fi/Ethernet cable.",
            "Alert IT Security team immediately via phone or helpdesk chat."
        ]
    }
]
