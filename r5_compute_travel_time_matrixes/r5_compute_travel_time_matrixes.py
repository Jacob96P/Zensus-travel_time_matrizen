# Angelehnt an https://github.com/DigitalGeographyLab/travel-time-matrix-computer/tree/main/src/travel_time_matrix_computer

import os
import r5py
import datetime
import configparser
from datetime import datetime, timedelta
from r5py import TransportMode
import geopandas as gpd
from time import time
from shapely.ops import unary_union
import logging
from pathlib import Path

def load_params_from_ini(config_file_path):
    config = configparser.ConfigParser()
    config.read(config_file_path)
    
    params = []
    for section in config.sections():
        if section == 'general':
            general_params = {
                'departure_times':[datetime.strptime(time.strip(), "%Y-%m-%d %H:%M") for time in config.get("general", "departure_times").split(",")],
                'buffer_distance_km':int(config[section]['buffer_distance_km']),
                'buffer_hamburg_km':int(config[section]['buffer_hamburg_km'])
            }
        else:
            # Dictionary für Parameter des Abschnitts erstellen
            param = {
                'mode': config[section]['mode'],
                'departure_time_window': timedelta(minutes=int(config[section]['departure_time_window'])),
                'transport_modes': [getattr(TransportMode, mode.strip()) for mode in config[section]['transport_modes'].split(',')],
                'snap_to_network': config[section].getboolean('snap_to_network'),
                'percentiles': [int(perc) for perc in config[section]['percentiles'].split(',')],
                'max_time': timedelta(minutes=int(config[section]['max_time'])),
                'max_time_walking': timedelta(minutes=int(config[section]['max_time_walking']))
            }
            params.append(param)
    
    return general_params, params





def create_transport_network(repoDirectoryPath, logger, kreis):
    name_kreis = kreis['GEN'].iloc[0]
    gtfs_files = [
        os.path.join(repoDirectoryPath, f'.zip')
    ]
    osm_network_file = os.path.join(repoDirectoryPath, 'osm.pbf')

    start_time2 = time()
    transport_network = r5py.TransportNetwork(
        osm_pbf = osm_network_file,
        gtfs = gtfs_files
        )
    logger.info(f'Transport Network für {name_kreis} erstellt;  Zeit: {round((time()-start_time2)/60, 2)} min')
    logger.info(f'GTFS-Files:  {gtfs_files}')
    logger.info(f'OSM-File:  {osm_network_file}')

    return transport_network




def calculate_travel_time_matrix(transport_network:r5py.TransportNetwork, 
                                 origins_grid:gpd.GeoDataFrame, 
                                 destinations:gpd.GeoDataFrame,
                                 departure:datetime,
                                 out_path,
                                 params:list,
                                 speeds=True,
                                 logger=None):
    start_time3 = time()

    if logger:
        logger.info(f"Calculating Travel Times for {departure}")
    else:
        print(f"Calculating Travel Times for {departure}")
    
    # origins vorbereiten
    if 'id' in origins_grid.columns:
        origins_grid.drop(columns=['id'], inplace=True)
    origins_grid['id'] = origins_grid.index
    origin_points = origins_grid.copy()
    origin_points = origin_points.to_crs(epsg=25832)
    origin_points['geometry'] = origin_points.centroid
    origin_points = origin_points.to_crs(epsg=4326)

    # destinations vorbereiten
    if 'id' in destinations.columns:
        destinations.drop(columns=['id'], inplace=True)
    destinations['id'] = destinations.index

    if speeds:
        walking_speeds = {
            "slow": 3.43,
            "avg": 4.7
        }
        cycling_speeds = {
            "slo": 11.75,
            "avg": 14.92,
            "fst": 18.09
        }
    else:
        walking_speeds = {
            "avg": 4.7
        }
        cycling_speeds = {
            "avg": 14.92
        }


    for i in range(len(params)):
        if params[i]['mode'] == 'WALK':
            for index, tupel in enumerate(walking_speeds.items()):
                key = tupel[0]
                value = tupel[1]

                if logger:
                    logger.info(f'PARAMS:')
                    logger.info(f'mode: {params[i]['mode']}')
                    logger.info(f'departure: {departure}')
                    logger.info(f'departure_time_window: {params[i]['departure_time_window']}')
                    logger.info(f'transport_modes: {params[i]['transport_modes']}')
                    logger.info(f'walking_speed: {value}')
                    logger.info(f'snap_to_network: {params[i]['snap_to_network']}')
                    logger.info(f'percentiles: {params[i]['percentiles']}')
                    logger.info(f'max_time: {params[i]['max_time']}')

                start_time = time()
                travel_time_matrix_computer = r5py.TravelTimeMatrixComputer(
                        transport_network,
                        origins=origin_points,
                        destinations=destinations,
                        departure=departure,
                        departure_time_window=params[i]['departure_time_window'],
                        transport_modes=params[i]['transport_modes'],
                        speed_walking=value,
                        snap_to_network=params[i]['snap_to_network'],
                        percentiles=params[i]['percentiles'],
                        max_time=params[i]['max_time']
                    )
                travel_times = travel_time_matrix_computer.compute_travel_times()

                travel_times = travel_times.set_index(["from_id", "to_id"])

                for perc in params[i]['percentiles']:
                    travel_times[f'travel_time_p{perc}'] = travel_times[f'travel_time_p{perc}'].astype('Int64')
                    travel_times = travel_times.rename(columns={f'travel_time_p{perc}': f'{params[i]['mode']}_{key}_p{perc}'})

                if i == 0 and index == 0:
                    merged_travel_times = travel_times
                else:
                    merged_travel_times = merged_travel_times.join(travel_times)

                for perc in params[i]['percentiles']:
                    if logger:
                        logger.info(f"Berechnung der Travel Times mit dem Mode '{params[i]['mode']}_{key}_p{perc}' abgeschlossen. Zeit: {round((time()-start_time)/60, 2)} min")
                    else:
                        print(f"Berechnung der Travel Times mit dem Mode '{params[i]['mode']}_{key}_p{perc}' abgeschlossen. Zeit: {round((time()-start_time)/60, 2)} min")

        if params[i]['mode'] == 'BICYCLE':
            for index, tupel in enumerate(cycling_speeds.items()):
                key = tupel[0]
                value = tupel[1]
                
                if logger:
                    logger.info(f'PARAMS:')
                    logger.info(f'mode: {params[i]['mode']}')
                    logger.info(f'departure: {departure}')
                    logger.info(f'departure_time_window: {params[i]['departure_time_window']}')
                    logger.info(f'transport_modes: {params[i]['transport_modes']}')
                    logger.info(f'walking_speed: {walking_speeds['avg']}')
                    logger.info(f'speed_cycling: {value}')
                    logger.info(f'snap_to_network: {params[i]['snap_to_network']}')
                    logger.info(f'percentiles: {params[i]['percentiles']}')
                    logger.info(f'max_time: {params[i]['max_time']}')

                start_time = time()
                travel_time_matrix_computer = r5py.TravelTimeMatrixComputer(
                        transport_network,
                        origins=origin_points,
                        destinations=destinations,
                        departure=departure,
                        departure_time_window=params[i]['departure_time_window'],
                        transport_modes=params[i]['transport_modes'],
                        speed_walking = walking_speeds['avg'],
                        speed_cycling=value,
                        snap_to_network=params[i]['snap_to_network'],
                        percentiles=params[i]['percentiles'],
                        max_time=params[i]['max_time'],
                    )
                travel_times = travel_time_matrix_computer.compute_travel_times()

                travel_times = travel_times.set_index(["from_id", "to_id"])

                for perc in params[i]['percentiles']:
                    travel_times[f'travel_time_p{perc}'] = travel_times[f'travel_time_p{perc}'].astype('Int64')
                    travel_times = travel_times.rename(columns={f'travel_time_p{perc}': f'{params[i]['mode']}_{key}_p{perc}'})

                if i == 0 and index == 0:
                    merged_travel_times = travel_times
                else:
                    merged_travel_times = merged_travel_times.join(travel_times)

                for perc in params[i]['percentiles']:
                    if logger:
                        logger.info(f"Berechnung der Travel Times mit dem Mode '{params[i]['mode']}_{key}_p{perc}' abgeschlossen. Zeit: {round((time()-start_time)/60, 2)} min")
                    else:
                        print(f"Berechnung der Travel Times mit dem Mode '{params[i]['mode']}_{key}_p{perc}' abgeschlossen. Zeit: {round((time()-start_time)/60, 2)} min")

        if params[i]['mode'] == 'TRANSIT':
            out_path += f'_{params[i]['departure_time_window']}'
            for index, tupel in enumerate(walking_speeds.items()):
                key = tupel[0]
                value = tupel[1]
                
                if logger:
                    logger.info(f'PARAMS:')
                    logger.info(f'mode: {params[i]['mode']}')
                    logger.info(f'departure: {departure}')
                    logger.info(f'departure_time_window: {params[i]['departure_time_window']}')
                    logger.info(f'transport_modes: {params[i]['transport_modes']}')
                    logger.info(f'walking_speed: {value}')
                    logger.info(f'snap_to_network: {params[i]['snap_to_network']}')
                    logger.info(f'percentiles: {params[i]['percentiles']}')
                    logger.info(f'max_time: {params[i]['max_time']}')
                    logger.info(f'max_time_walking: {params[i]['max_time_walking'] if params[i]['max_time_walking'] != 0 else params[i]['max_time']}')

                start_time = time()
                travel_time_matrix_computer = r5py.TravelTimeMatrixComputer(
                        transport_network,
                        origins=origin_points,
                        destinations=destinations,
                        departure=departure,
                        departure_time_window=params[i]['departure_time_window'],
                        transport_modes=params[i]['transport_modes'],
                        speed_walking=value,
                        snap_to_network=params[i]['snap_to_network'],
                        percentiles=params[i]['percentiles'],
                        max_time=params[i]['max_time'],
                        max_time_walking=params[i]['max_time_walking'] if params[i]['max_time_walking'] != 0 else params[i]['max_time']
                    )
                travel_times = travel_time_matrix_computer.compute_travel_times()

                travel_times = travel_times.set_index(["from_id", "to_id"])

                for perc in params[i]['percentiles']:
                    travel_times[f'travel_time_p{perc}'] = travel_times[f'travel_time_p{perc}'].astype('Int64')
                    travel_times = travel_times.rename(columns={f'travel_time_p{perc}': f'{params[i]['mode']}_{key}_p{perc}'})

                if i == 0 and index == 0:
                    merged_travel_times = travel_times
                else:
                    merged_travel_times = merged_travel_times.join(travel_times)

                for perc in params[i]['percentiles']:
                    if logger:
                        logger.info(f"Berechnung der Travel Times mit dem Mode '{params[i]['mode']}_{key}_p{perc}' abgeschlossen. Zeit: {round((time()-start_time)/60, 2)} min")
                    else:
                        print(f"Berechnung der Travel Times mit dem Mode '{params[i]['mode']}_{key}_p{perc}' abgeschlossen. Zeit: {round((time()-start_time)/60, 2)} min")        

        if params[i]['mode'] == 'CAR':
            for index, tupel in enumerate(walking_speeds.items()):
                key = tupel[0]
                value = tupel[1]
                
                if logger:
                    logger.info(f'PARAMS:')
                    logger.info(f'mode: {params[i]['mode']}')
                    logger.info(f'departure: {departure}')
                    logger.info(f'departure_time_window: {params[i]['departure_time_window']}')
                    logger.info(f'transport_modes: {params[i]['transport_modes']}')
                    logger.info(f'speed_walking: {walking_speeds['avg']}')
                    logger.info(f'snap_to_network: {params[i]['snap_to_network']}')
                    logger.info(f'percentiles: {params[i]['percentiles']}')
                    logger.info(f'max_time: {params[i]['max_time']}')

                start_time = time()
                travel_time_matrix_computer = r5py.TravelTimeMatrixComputer(
                        transport_network,
                        origins=origin_points,
                        destinations=destinations,
                        departure=departure,
                        departure_time_window=params[i]['departure_time_window'],
                        transport_modes=params[i]['transport_modes'],
                        speed_walking = walking_speeds['avg'],
                        snap_to_network=params[i]['snap_to_network'],
                        percentiles=params[i]['percentiles'],
                        max_time=params[i]['max_time']
                    )
                travel_times = travel_time_matrix_computer.compute_travel_times()

                travel_times = travel_times.set_index(["from_id", "to_id"])

                for perc in params[i]['percentiles']:
                    travel_times[f'travel_time_p{perc}'] = travel_times[f'travel_time_p{perc}'].astype('Int64')
                    travel_times = travel_times.rename(columns={f'travel_time_p{perc}': f'{params[i]['mode']}_{key}_p{perc}'})

                if i == 0 and index == 0:
                    merged_travel_times = travel_times
                else:
                    merged_travel_times = merged_travel_times.join(travel_times)

                for perc in params[i]['percentiles']:
                    if logger:
                        logger.info(f"Berechnung der Travel Times mit dem Mode '{params[i]['mode']}_{key}_p{perc}' abgeschlossen. Zeit: {round((time()-start_time)/60, 2)} min")
                    else:
                        print(f"Berechnung der Travel Times mit dem Mode '{params[i]['mode']}_{key}_p{perc}' abgeschlossen. Zeit: {round((time()-start_time)/60, 2)} min")

    logger.info(f'TravelTime Matrix erstellt;  Zeit: {round((time()-start_time3)/60, 2)} min')


    
    merged_travel_times = merged_travel_times.reset_index()
    merged_travel_times = merged_travel_times.dropna(how='all', subset=travel_times.columns.difference(['from_id', 'to_id'])) # Reihen mit ausschließlich NaN entfernen, halbiert Datenmenge

    merged_travel_times.to_csv(f'{out_path}.csv')
    if logger:
        logger.info(f"Datei unter '{out_path}' gespeichert.")
    else:
        print(f"Datei unter '{out_path}' gespeichert.")

    return merged_travel_times




def calculate_detailed_iternaries_matrix(transport_network:r5py.TransportNetwork, 
                                 origins_grid:gpd.GeoDataFrame, 
                                 destinations:gpd.GeoDataFrame,
                                 departure:datetime,
                                 out_path,
                                 param):

    # origins vorbereiten
    if 'id' in origins_grid.columns:
        origins_grid.drop(columns=['id'], inplace=True)
    origins_grid['id'] = origins_grid.index
    origin_points = origins_grid.copy()
    origin_points = origin_points.to_crs(epsg=25832)
    origin_points['geometry'] = origin_points.centroid
    origin_points = origin_points.to_crs(epsg=4326)

    # destinations vorbereiten
    if 'id' in destinations.columns:
        destinations.drop(columns=['id'], inplace=True)
    destinations['id'] = destinations.index

    start_time = time()

    detailed_iternariescomputer = r5py.DetailedItinerariesComputer(
            transport_network,
            origins=origin_points,
            destinations=destinations,
            departure=departure,
            departure_time_window=param['departure_time_window'],
            transport_modes=param['transport_modes'],
            speed_walking=param['speed_walking'],
            snap_to_network=param['snap_to_network'],
            percentiles=[1],
            max_time=param['max_time'],
            max_time_walking=param['max_time_walking'] if param['max_time_walking'] != 0 else param['max_time']
        )
    travel_times = detailed_iternariescomputer.compute_travel_details()

    travel_times = travel_times.set_index(["from_id", "to_id"])
    
    print(f"Berechnung der Detailed Travel Times mit dem Mode '{param['column_name']}' abgeschlossen. Zeit: {round((time()-start_time)/60, 2)} min")
    
    travel_times.to_csv(out_path)
    print(f"\nDatei unter '{out_path}' gespeichert")

    return travel_times





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

    gdf_buffered['geometry'] = gdf['geometry'].buffer(buffer_distance_km * 1000)

    if hamburg_gdf is not None:
        hamburg_gdf = hamburg_gdf.to_crs(epsg=3857)
        hamburg_union = unary_union(hamburg_gdf['geometry'])
        gdf_buffered['geometry'] = gdf_buffered['geometry'].difference(hamburg_union)

        gdf['geometry'] = gdf['geometry'].buffer(buffer_hamburg * 1000)

        first_index = gdf_buffered.index[0]
        gdf_buffered.at[first_index, 'geometry'] = gdf_buffered.at[first_index, 'geometry'].union(gdf.at[first_index, 'geometry'])

    gdf_buffered = gdf_buffered.to_crs(epsg=orig_epsg)

    return gdf_buffered





def get_logger(path):
    if not Path(path).is_dir():
        os.mkdir(path)
    logger = logging.getLogger(__name__)
    if logger.hasHandlers():
        logger.handlers.clear()
    logfile_name = os.path.join('./logs', f"LOG_TravelTimes_{datetime.now().strftime('%Y_%m_%d__%H_%M')}")
    # Set up the logger configuration
    file_handler = logging.FileHandler(logfile_name, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    # Stream-Handler (für die Konsole) erstellen und hinzufügen
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)

    return logger