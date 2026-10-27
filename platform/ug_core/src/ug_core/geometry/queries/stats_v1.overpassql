[out:json][timeout:240];
way["highway"]({{bbox}});
for(t["highway"]) { make stat group="highway",value=_.val,ways=count(ways),km=sum(length())/1000; out; }
way["landuse"]({{bbox}});
for(t["landuse"]) { make stat group="landuse",value=_.val,ways=count(ways); out; }
(way["building"]({{bbox}}); relation["building"]({{bbox}}););
make stat group="buildings",value="all",ways=count(ways),relations=count(relations); out;
way["building"]["building:levels"]({{bbox}});
make stat group="buildings",value="with_levels",ways=count(ways); out;
way["highway"]["name"]({{bbox}});
make stat group="names",value="named_highways",ways=count(ways); out;
way["highway"](newer:"{{one_year_ago}}")({{bbox}});
make stat group="freshness",value="highways_edited_last_year",ways=count(ways); out;
way["highway"](newer:"{{two_years_ago}}")({{bbox}});
make stat group="freshness",value="highways_edited_last_two_years",ways=count(ways); out;
nwr["amenity"~"^(school|university|college|hospital|clinic|place_of_worship|police|fire_station|townhall)$"]({{bbox}});
for(t["amenity"]) { make stat group="amenity",value=_.val,n=count(nodes)+count(ways)+count(relations); out; }
nwr["office"="government"]({{bbox}});
make stat group="amenity",value="office_government",n=count(nodes)+count(ways)+count(relations); out;
nwr["leisure"~"^(park|garden|pitch|stadium|sports_centre)$"]({{bbox}});
for(t["leisure"]) { make stat group="leisure",value=_.val,n=count(nodes)+count(ways)+count(relations); out; }
nwr["man_made"~"^(water_tower|reservoir_covered|water_works|pumping_station|storage_tank|wastewater_plant|pipeline|water_well)$"]({{bbox}});
for(t["man_made"]) { make stat group="water_infrastructure",value=_.val,n=count(nodes)+count(ways)+count(relations); out; }
