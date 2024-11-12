# Zensus-travel_time_matrizen

>Angelehnt an https://github.com/DigitalGeographyLab/travel-time-matrix-computer/tree/main/src/travel_time_matrix_computer

## Inhalt:
* Python-basierte Analyse zum erstellen von TravelTimeMatrizen mit r5py (https://r5py.readthedocs.io/en/stable/reference/reference.html) inklusive Workflow zum Vorbereiten der GTFS-OSM und bei Bedarf Zensus-Daten.
* Die Ziele der Analyse können variabel angepasst werden
* Das Filtern der Netzwerkdaten optimiert die Laufzeit, sodass auch ein Desktop-Computer Analysen für eine große Region in Deutschland rechnen kann.

## Daten:
* Origins: Zensus 100m-Gitterzellen  
 -> 2022: https://www.zensus2022.de/DE/Ergebnisse-des-Zensus/gitterzellen.html  
 -> 2011: https://www.zensus2011.de/DE/Home/Aktuelles/DemografischeGrunddaten.html  
* Netzwerk: osm-pbf -> https://download.geofabrik.de
* GTFS: DELFI fahrpläne Gesamtdeutschland  
 -> https://www.delfi.de/de/aktuelles/  
 -> Möglicherweise sind andere GTFS-Datensätze je nach Region vollständiger

* Quelle: Studienprojekt