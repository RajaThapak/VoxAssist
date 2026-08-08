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
    }
]
