from shapely.geometry import Polygon
import os
import gtfs_kit as gk
import pyrosm
import subprocess
import geopandas as gpd
import numpy as np
import time
from shapely.ops import unary_union


def GTFS_to_gpkg(in_gtfs_zip, out_dir, types):
    feed = gk.feed.read_feed(in_gtfs_zip, 'km')

    out_name = os.path.basename(in_gtfs_zip)[:-4]

    try:
        if 'stops' in types:
            stops_gdf = feed.get_stops(as_gdf=True)
            if not os.path.exists(out_dir):
                os.mkdir(out_dir)
            stops_gdf.to_file(os.path.join(out_dir, f'stops_{out_name}.gpkg'), driver='GPKG')
    except Exception as e:
        print('Fehler bei stops: ', e)

    try:
        if 'routes' in types:
            routes_gdf = feed.get_routes(as_gdf=True)
            if not os.path.exists(out_dir):
                os.mkdir(out_dir)
            routes_gdf.to_file(os.path.join(out_dir, f'routes_{out_name}.gpkg'), driver='GPKG')
    except Exception as e:
         print('Fehler bei routes: ', e)

    try:
        if 'trips' in types:
            trips_gdf = feed.get_trips(as_gdf=True)
            if not os.path.exists(out_dir):
                os.mkdir(out_dir)
            trips_gdf.to_file(os.path.join(out_dir, f'trips_{out_name}.gpkg'), driver='GPKG')
    except Exception as e:
         print('Fehler bei trips: ', e)

    try:
        if 'shapes' in types:
            shapes_gdf = feed.get_shapes(as_gdf=True)
            if not os.path.exists(out_dir):
                os.mkdir(out_dir)
            shapes_gdf.to_file(os.path.join(out_dir, f'shapes_{out_name}.gpkg'), driver='GPKG')
    except Exception as e:
         print('Fehler bei shapes: ', e)




def OSM_PBF_zuschneiden(name_kreis, bounding_gdf, in_pbf, out_dir, export_to_gpkg=True):

    boundingBox_coords = bounding_gdf.bounds.iloc[0].tolist()     # Format: xmin, ymin, xmax, ymax
    coords = [
        (boundingBox_coords[0], boundingBox_coords[1]), 
        (boundingBox_coords[0], boundingBox_coords[3]), 
        (boundingBox_coords[2], boundingBox_coords[3]), 
        (boundingBox_coords[2], boundingBox_coords[1]), 
        (boundingBox_coords[0], boundingBox_coords[1])
        ]
    BoundingBox = Polygon(coords)

    bbox = ','.join([str(item) for item in boundingBox_coords])
    if not os.path.exists(out_dir):
            os.mkdir(out_dir)
    out_path = os.path.join(out_dir, f'{name_kreis}_osm.pbf')

    # PBF Datensatz ausschneiden auf Bounding Box um Segeberg
    command = [
        "osmium", "extract",
        "--strategy", "complete_ways",
        "--bbox", bbox,
        in_pbf,
        "-o", out_path,
        "--overwrite"
    ]
    result = subprocess.run(command, capture_output=True, text=True)

    new_out_dir = os.path.join(out_dir, 'pbf_gpkg')
    if export_to_gpkg:
        osm = pyrosm.OSM(out_path, bounding_box=BoundingBox)
        walk = osm.get_network("walking")
        walk = walk[['osm_type','geometry','length']]
        if not os.path.exists(new_out_dir):
            os.mkdir(new_out_dir)
        walk.to_file(os.path.join(new_out_dir, f'{name_kreis}_osm_pbf.gpkg'), driver='GPKG')

    return result




def Zensus_2022_Gitterzellen_zuschneiden(directory_with_csv_files, out_dir, bounding_shape, name_kreis):
    '''
    Zensus2022
    Zensus Gitterzellen auf csv importieren, zuschneiden, verschiedene Parameter (demographie) mergen und exportieren (gpkg)
    '''
    try:
        c = 0
        for csvfile in os.listdir(directory_with_csv_files):
            if csvfile[-4:] == '.csv':
                start_time = time.time()
                path_to_csv = os.path.join(directory_with_csv_files, csvfile)
                gdf = gpd.GeoDataFrame.from_file(path_to_csv)

                # id korrigieren
                gdf['GITTER_ID_100m'] = gdf['GITTER_ID_100m'].str[10:]
                gdf['GITTER_ID_100m'] = gdf['GITTER_ID_100m'].str.replace('00E', 'E')
                # datentypen anpassen
                gdf['GITTER_ID_100m'] = gdf['GITTER_ID_100m'].astype(str)
                gdf['x_mp_100m'] = gdf['x_mp_100m'].astype(int)
                gdf['y_mp_100m'] = gdf['y_mp_100m'].astype(int)

                # geometry hinzufügen
                gdf['geometry'] = gdf.apply(lambda row: Polygon([
                    (row['x_mp_100m']-50, row['y_mp_100m']-50),  # Unten links
                    (row['x_mp_100m']-50, row['y_mp_100m']+50),  # Oben links
                    (row['x_mp_100m']+50, row['y_mp_100m']+50),  # Oben rechts
                    (row['x_mp_100m']+50, row['y_mp_100m']-50),  # Unten rechts
                    (row['x_mp_100m']-50, row['y_mp_100m']-50)   # Zurück zum Startpunkt
                ]), axis=1)

                gdf = gpd.GeoDataFrame(gdf, geometry='geometry')

                # crs anpassen zu WGS84
                gdf = gdf.set_crs("EPSG:3035")
                gdf = gdf.to_crs(epsg=4326)

                # auf area of interest filtern
                gdf = gdf[gdf.geometry.intersects(bounding_shape)]

                # Spalte anpassen (vierte spalte ist immer das inhaltsfeld)
                gdf[gdf.columns[3]] = gdf[gdf.columns[3]].str.replace('–', '').str.replace(',', '.').replace('-', np.nan).replace('', np.nan).astype(float)

                if c == 0:
                    merged_gdf = gdf
                elif c > 0:
                    merged_gdf = merged_gdf.merge(gdf[['GITTER_ID_100m', gdf.columns[3]]], on='GITTER_ID_100m')
                
                print(int((time.time()-start_time)))
                print(f'Erste Datei "{csvfile}" zugeschnitten und angepasst:  ', gdf.shape)
                c+= 1
        
        merged_gdf = merged_gdf.drop(columns=['x_mp_100m', 'y_mp_100m', 'werterlaeuternde_Zeichen'])

        # Prozentuale Anteile in Dezimal umrechnen
        merged_gdf['AnteilUnter18'] = merged_gdf['AnteilUnter18'] /100
        merged_gdf['AnteilUeber65'] = merged_gdf['AnteilUeber65'] / 100

        # Absolute Zahlen berechnen wie in Zensus 2011
        merged_gdf['unter18'] = round(merged_gdf['AnteilUnter18'] * merged_gdf['Einwohner'], 2)
        merged_gdf['ueber65'] = round(merged_gdf['AnteilUeber65'] * merged_gdf['Einwohner'], 2)

        new_out_dir = os.path.join(out_dir, name_kreis)
        if not os.path.exists(new_out_dir):
                os.mkdir(new_out_dir)
        out_path = os.path.join(new_out_dir, f'{name_kreis}_ZensusGitter.gpkg')
        merged_gdf.to_file(out_path, driver='GPKG')

        print(f'Dateien gemerged und nach {out_path} exportiert. Shape:  ')
    
        return {
            'success': True,
            'out_path': out_path,
            'Exception': False
        }

    except Exception as e:
        return {
            'success': False,
            'out_archive': False,
            'Exception': f'Exception: {e}'
        }



def Zensus_2011_Gitterzellen_zuschneiden(bevoelkerung_path, demographie_path, out_path, bounding_shape):
    '''
    Zensus Gitterzellen auf csv importieren, zuschneiden, verschiedene Parameter (demographie) mergen und exportieren (gpkg)
    :: bevoelkerung_path    bevölkerungsdaten Zensus 2011 csv-file
    :: demographie_path     demografiedaten Zensus 2011 csv-file
    :: out_path             pfad unter dem output geopackage gespeichert wird
    :: bounding_shape       Region auf das gefiltert wird als Shapely.Polygon
    '''
    start_time = time.time()

    # erste datei einlesen
    bev_gdf = gpd.read_file(bevoelkerung_path, sep=';')
    print('Eingelesen; ', 'Zeit:  ', round((time.time()-start_time)/60,2), ' min')

    # datentypen anpassen
    bev_gdf['Gitter_ID_100m'] = bev_gdf['Gitter_ID_100m'].astype(str)

    # grob filtern über 100km gitter
    list_zellen_north = ['N32', 'N33', 'N34']
    list_zellen_east = ['E41', 'E42', 'E43', 'E44', 'E45']
    for i in list_zellen_north:
        bev_gdf = bev_gdf[bev_gdf['Gitter_ID_100m'].apply(lambda x: any(substring in x for substring in list_zellen_north))]
        bev_gdf = bev_gdf[bev_gdf['Gitter_ID_100m'].apply(lambda x: any(substring in x for substring in list_zellen_east))]
    print('über 100km gitter gefiltert; ', 'Zeit:  ', round((time.time()-start_time)/60,2), ' min')

    bev_gdf['x_mp_100m'] = bev_gdf['x_mp_100m'].astype(int)
    bev_gdf['y_mp_100m'] = bev_gdf['y_mp_100m'].astype(int)
    print('Datentypen angepasst; ', 'Zeit:  ', round((time.time()-start_time)/60,2), ' min')

    # geometry hinzufügen
    bev_gdf['geometry'] = bev_gdf.apply(lambda row: Polygon([
        (row['x_mp_100m']-50, row['y_mp_100m']-50),  # Unten links
        (row['x_mp_100m']-50, row['y_mp_100m']+50),  # Oben links
        (row['x_mp_100m']+50, row['y_mp_100m']+50),  # Oben rechts
        (row['x_mp_100m']+50, row['y_mp_100m']-50),  # Unten rechts
        (row['x_mp_100m']-50, row['y_mp_100m']-50)   # Zurück zum Startpunkt
    ]), axis=1)
    bev_gdf = gpd.GeoDataFrame(bev_gdf, geometry='geometry')
    print('Geometrie hinzugefügt; ', 'Zeit:  ', round((time.time()-start_time)/60,2), ' min')

    # # crs anpassen zu WGS84
    bev_gdf = bev_gdf.set_crs("EPSG:3035")
    bev_gdf = bev_gdf.to_crs(epsg=4326)
    print('crs angepasst; ', 'Zeit:  ', round((time.time()-start_time)/60,2), ' min')

    # # auf area of interest filtern
    bev_gdf = bev_gdf[bev_gdf.geometry.intersects(bounding_shape)]
    print(f'Auf bounding_shape Zugeschnitten; ', 'Zeit:  ', round((time.time()-start_time)/60,2), ' min')

    # # Spalte anpassen
    name_vierte_spalte= bev_gdf.columns[3]
    bev_gdf[name_vierte_spalte] = bev_gdf[name_vierte_spalte].str.replace('–', '').str.replace(',', '.').replace('-', np.nan).replace('-1', np.nan).replace('', np.nan).astype(float)
    print('daten angepasst; ', 'Zeit:  ', round((time.time()-start_time)/60,2), ' min')

    # jetzt dem laden
    bev_dem = gpd.read_file(demographie_path, sep=';', encoding='latin1', columns=['Gitter_ID_100m', 'Merkmal', 'Auspraegung_Code', 'Anzahl'])
    print('Tabelle dem eingelesen; ', 'Zeit:  ', round((time.time()-start_time)/60,2), ' min')

    # datentypen anpassen
    bev_dem['Gitter_ID_100m'] = bev_dem['Gitter_ID_100m'].astype(str)
    bev_dem['Merkmal'] = bev_dem['Merkmal'].astype(str)
    bev_dem['Auspraegung_Code'] = bev_dem['Auspraegung_Code'].astype(int)
    bev_dem['Anzahl'] = bev_dem['Anzahl'].astype(int)

    # filtern
    bev_dem = bev_dem[bev_dem['Merkmal'] == 'ALTER_KURZ']
    bev_dem = bev_dem[bev_dem['Auspraegung_Code'].isin([1,5])]
    print('Tabelle dem gefiltert; ', 'Zeit:  ', round((time.time()-start_time)/60,2), ' min')

    # Pivot-Tabelle erstellen
    bev_dem = bev_dem.pivot_table(
        index='Gitter_ID_100m',              # Eindeutige IDs als Index
        columns='Auspraegung_Code',           # Codes werden zu Spalten
        values='Anzahl',                      # Die Werte, die wir in die neuen Zellen setzen
        aggfunc='first',                      # Aggregationsfunktion, 'first' reicht, da es nur eine Zeile pro Kombination gibt
        fill_value=0                          # Fehlende Werte mit 0 auffüllen
    )
    print('Pivot-Tabelle erstellt; ', 'Zeit:  ', round((time.time()-start_time)/60,2), ' min')

    bev_dem = bev_dem.rename(columns={1: 'unter18', 5: 'ueber65'})
    bev_dem = bev_dem.reset_index(drop=False)
    print('dem Spalten umbenannt; ', 'Zeit:  ', round((time.time()-start_time)/60,2), ' min')

    bev_gdf = bev_gdf.merge(bev_dem[['Gitter_ID_100m', 'unter18', 'ueber65']], on='Gitter_ID_100m')
    bev_dem = None # damit das aus dem speicher verschwindet
    print('Gemerged; ', 'Zeit:  ', round((time.time()-start_time)/60,2), ' min')

    print('Unwichtige Spalten entfernt; ', 'Zeit:  ', round((time.time()-start_time)/60,2), ' min')
    # Prozentuale Anteile berechnen (dezimal)
    bev_gdf['AnteilUnter18'] = round(bev_gdf['unter18'] / bev_gdf['Einwohner'], 2)
    bev_gdf['AnteilUeber65'] = round(bev_gdf['ueber65'] / bev_gdf['Einwohner'], 2)
    print('prozentuale anteile berechnet; ', 'Zeit:  ', round((time.time()-start_time)/60,2), ' min')
    out_dir = os.path.dirname(out_path)
    if not os.path.exists(out_dir):
            os.mkdir(out_dir)

    bev_gdf.to_file(out_path, driver='GPKG')

    print('Zeit:  ', round((time.time()-start_time)/60,2), ' min')
    print(f'Dateien gemerged und nach {out_path} exportiert. Shape: ')
    print(bev_gdf.shape)

    return bev_gdf






def buffer_geometries(gdf, buffer_distance_km=20, hamburg_gdf=None, buffer_hamburg=5):
    """
    Notwendig weil nicht alle crs in meter sind (4326 in grad)

    Parameters:
    gdf: gdf dessen geoms gebuffert werden
    buffer_distance_km: buffer-distanz in km 

    Returns:
    gebufferten gdf
    """
    try:
        orig_epsg = gdf.crs.to_epsg()
    except:
        raise ValueError("GDF hat kein crs")
    gdf = gdf.to_crs(epsg=3857)
    gdf_buffered = gdf.copy()

    # buffer
    gdf_buffered['geometry'] = gdf['geometry'].buffer(buffer_distance_km * 1000)

    if hamburg_gdf is not None:
        hamburg_gdf = hamburg_gdf.to_crs(epsg=3857)
        hamburg_union = unary_union(hamburg_gdf['geometry'])
        gdf_buffered['geometry'] = gdf_buffered['geometry'].difference(hamburg_union)

        # buffer wenn hamburg angrenzt
        gdf['geometry'] = gdf['geometry'].buffer(buffer_hamburg * 1000)

        # merge der gebufferten regionen
        first_index = gdf_buffered.index[0]
        gdf_buffered.at[first_index, 'geometry'] = gdf_buffered.at[first_index, 'geometry'].union(gdf.at[first_index, 'geometry'])

    # Zurück zum alten crs
    gdf_buffered = gdf_buffered.to_crs(epsg=orig_epsg)

    return gdf_buffered