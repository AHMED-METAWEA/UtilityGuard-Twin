[out:json][timeout:240];
way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|service|living_street|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link|construction)$"]({{bbox}});
out geom qt;
