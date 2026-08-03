Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """C:\Users\user\AppData\Local\Programs\Python\Python313\pythonw.exe"" ""d:\2026AI_agent\RQD\server.py""", 0, False
WScript.Sleep 1500
WshShell.Run "http://localhost:8000"
