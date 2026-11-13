import os
d=os.path.dirname(os.path.abspath(__file__))
h=open(os.path.join(d,"app.html")).read()
h=h.replace("/*LEAFLETCSS*/",open(os.path.join(d,"leaflet.css")).read()).replace("/*DATAJS*/",open(os.path.join(d,"data.js")).read())
open(os.path.join(d,"skatekartan.html"),"w").write(h); print(len(h)//1024,"KB")
