
# Spatial filtering of a GTFS-Dataset

# Bibliotheken laden
library(gtfstools)
library(sf)

# Pfad zur GTFS-zip und Geopackage
gtfs_path <- ""
gpkg_path <- ""

# GTFS laden
gtfs_data <- read_gtfs(gtfs_path)

# Kreise laden
shapes_gdf <- st_read(gpkg_path, layer = "Kreise_MRH_Zensus")

# Out dir
output_dir <- ""
if (!dir.exists(output_dir)) {
  dir.create(output_dir, recursive = TRUE)
}

# Für Output-Filename
attribut_spalte <- "GEN"

# Filterung und Speicherung
for (i in seq_len(nrow(shapes_gdf))) {

  geom <- shapes_gdf[i, ]
  attribut_wert <- geom[[attribut_spalte]]

  # Transformation in metrisches CRS für Puffer
  geom_metrisch <- st_transform(geom, crs = 3857)

  # Puffern
  geom_buffered <- st_buffer(geom_metrisch, dist = 20000)  # 2000m -> 20 km

  # Zurück in WGS84
  geom_buffered <- st_transform(geom_buffered, crs = 4326)

  # GTFS-Daten filtern
  gtfs_filtered <- filter_by_spatial_extent(
    gtfs = gtfs_data,
    geom = geom_buffered,
    spatial_operation = sf::st_intersects,
    keep = TRUE
  )

  # Exportieren
  output_filename <- paste0("DELFI_gtfs_filtered_", attribut_wert, ".zip")
  output_filepath <- file.path(output_dir, output_filename)
  write_gtfs(gtfs_filtered, output_filepath)

  message("GTFS Exportiert: ", output_filepath)
}