import os
import sys
import time
import win32com.client

src = os.path.abspath(sys.argv[1])
dst = os.path.abspath(sys.argv[2])

app = win32com.client.Dispatch("PowerPoint.Application")
app.Visible = 1  # manche PowerPoint-Builds verlangen eine sichtbare Instanz fuer Export
pres = app.Presentations.Open(src, WithWindow=False)
time.sleep(1)
pres.SaveAs(dst, 32)  # 32 = ppSaveAsPDF
pres.Close()
app.Quit()
print("done")
