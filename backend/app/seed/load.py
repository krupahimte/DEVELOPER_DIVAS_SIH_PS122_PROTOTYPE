"""Seed step 1: write the plan-side sample files and load master data into the DB.

sample_data/schedule_xer.csv      XER-like schedule (the match target)
sample_data/geofences.geojson     10 work-front polygons
The DB is then loaded *from those files* (the XER parser is exercised for real).
"""
import json
from datetime import date

from sqlmodel import Session

from .. import config
from ..models import (Activity, Contractor, Equipment, Line, MaterialIssue, ObjectItem, Permit, Reporter, WeatherObs, WorkFront)
from ..pipeline import xer_parse
from . import master as M


def write_plan_files():
    config.SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    # geofences
    feats = []
    for wid, name, unit, area, box, aliases in M.WORK_FRONTS:
        feats.append({"type": "Feature", "properties": {"id": wid, "name": name, "unit": unit, "area": area},
                      "geometry": {"type": "Polygon", "coordinates": [M.polygon(box)]}})
    (config.SAMPLE_DIR / "geofences.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, indent=1))
    # schedule
    rows = []
    for (aid, name, disc, unit, wf, action, ocls, line, ps, pf, preds, scope, permit) in M.ACTIVITIES:
        area = next((w[3] for w in M.WORK_FRONTS if w[0] == wf), "Fabrication Shop")
        con = M.DISC_CONTRACTOR.get(disc)
        pkg = next((c[2] for c in M.CONTRACTORS if c[0] == con), "")
        rows.append({"task_code": aid, "wbs": M.wbs_for(aid, disc, unit, wf), "task_name": name, "discipline": disc, "unit": unit,
                     "area": area, "work_front": wf or "", "target_start_date": ps.isoformat(), "target_end_date": pf.isoformat(),
                     "act_start_date": "", "act_end_date": "", "pred_task_codes": ";".join(preds), "scope_objects": ";".join(scope),
                     "permit_type": permit or "", "contractor": con or "", "scope_package": pkg, "action": action, "object_class": ocls,
                     "line_no": line or ""})
    xer_parse.write(config.SAMPLE_DIR / "schedule_xer.csv", rows)


def load_master(session: Session):
    gj = json.loads((config.SAMPLE_DIR / "geofences.geojson").read_text())
    alias_map = {w[0]: w[5] for w in M.WORK_FRONTS}
    for f in gj["features"]:
        p = f["properties"]
        ring = f["geometry"]["coordinates"][0]
        lats = [c[1] for c in ring[:-1]]
        lons = [c[0] for c in ring[:-1]]
        session.add(WorkFront(id=p["id"], name=p["name"], unit=p["unit"], area=p["area"], polygon=ring,
                              centroid_lat=sum(lats) / len(lats), centroid_lon=sum(lons) / len(lons), aliases=alias_map[p["id"]]))
    for line_no, dwg, system, unit, spools in M.LINES:
        session.add(Line(line_no=line_no, drawing_no=dwg, system=system, unit=unit))
        for n, wf in spools.items():
            sid = M.spool_id(line_no, n)
            session.add(ObjectItem(object_id=sid, object_class="spool", parent=line_no, ordinal=n, work_front=wf,
                                   label=f"Spool {n} of {line_no}"))
    seen = {M.spool_id(l[0], n) for l in M.LINES for n in l[4]}
    for (aid, name, disc, unit, wf, action, ocls, line, ps, pf, preds, scope, permit) in M.ACTIVITIES:
        for so in scope:
            if so in seen:
                continue
            seen.add(so)
            ordinal = None
            if so.startswith("FDN-F-"):
                cls, ordinal = "foundation", int(so.split("-")[-1])
            elif so.startswith("TRAY-T-"):
                cls, ordinal = "tray", int(so.split("-")[-1])
            elif so.startswith("LOOP-"):
                cls = "loop"
            else:
                cls = ocls
            session.add(ObjectItem(object_id=so, object_class=cls, ordinal=ordinal, work_front=wf, label=so))
    for cid, name, pkg, discs in M.CONTRACTORS:
        session.add(Contractor(id=cid, name=name, scope_package=pkg, disciplines=discs))
    for rid, name, name_hi, role, disc, con, wfs, lang in M.REPORTERS:
        session.add(Reporter(id=rid, name=name, name_hi=name_hi, role=role, discipline=disc, contractor=con, work_fronts=wfs, language=lang))
    for row in xer_parse.parse(config.SAMPLE_DIR / "schedule_xer.csv"):
        session.add(Activity(**row))
    for pid, ptype, wf, vf, vt, status, gas in M.PERMITS:
        session.add(Permit(permit_id=pid, permit_type=ptype, work_front=wf, valid_from=vf, valid_to=vt, status=status, gas_test_done=gas))
    for item, desc, status, wf in M.material_issues():
        session.add(MaterialIssue(item_id=item, description=desc, status=status, work_front=wf))
    for eid, typ, wf, status in M.EQUIPMENT:
        session.add(Equipment(equipment_id=eid, type=typ, work_front=wf, status=status))
    for d, rain, tmax, wind, hourly in M.weather_days():
        session.add(WeatherObs(day=d, rain_mm=rain, temp_max=tmax, wind_kmph=wind, hourly_rain=hourly))
    session.commit()
    # baseline actuals imported from the PMIS (before go-live on 5 Sep)
    for aid, (s, f) in M.BASELINE_ACTUALS.items():
        a = session.get(Activity, aid)
        a.actual_start = date.fromisoformat(s)
        a.actual_start_prov = "HUMAN"
        if f:
            a.actual_finish = date.fromisoformat(f)
            a.actual_finish_prov = "HUMAN"
        session.add(a)
    session.commit()
