// Route-to-stops mappings — defines which layer keys belong together as a group.
// linearLayerKey: the LayerState key controlling the linear (line) feature
// stopLayerKey:   the LayerState key controlling the associated point features

export interface RouteGroupMapping {
  displayName: string;
  groupedKey: string;
  linearLayerKey: string;
  stopLayerKey: string;
  routes: string[];
}

export const ROUTE_STOP_MAPPINGS: Record<string, RouteGroupMapping> = {
  trails: {
    displayName: 'Historic Trails',
    groupedKey: 'grouped_trails',
    linearLayerKey: 'trail',
    stopLayerKey: 'trail_landmark',
    routes: [
      'Oregon Trail',
      'California Trail',
      'Santa Fe Trail',
      'Mormon Trail',
      'Bozeman Trail',
      'Natchez Trace',
      'Old Spanish Trail',
      'Gila Trail',
      'El Camino Real de Tierra Adentro',
      'Wilderness Road',
      'Great Wagon Road',
      'Chisholm Trail',
      'Goodnight-Loving Trail',
      'Western Trail',
      'Shawnee Trail',
      'Smoky Hill Trail',
      'Lander Road',
      'Mullan Road',
      'Nez Perce Trail',
    ],
  },
  stagecoach: {
    displayName: 'Stagecoach Routes',
    groupedKey: 'grouped_stagecoach',
    linearLayerKey: 'road',
    stopLayerKey: 'stagecoach_stop',
    routes: [
      'Butterfield Overland Mail',
      'San Antonio and San Diego Mail Line',
      "Central Overland California and Pike's Peak Express",
      'Holladay Overland Mail and Express',
      'Overland Stage to Denver',
    ],
  },
  railroads: {
    displayName: 'Railroad Lines',
    groupedKey: 'grouped_railroads',
    linearLayerKey: 'railroad',
    stopLayerKey: 'railroad_stop',
    routes: [], // auto-detected from linear features
  },
  pony_express: {
    displayName: 'Pony Express',
    groupedKey: 'grouped_pony_express',
    // The Pony Express route line is rendered as part of the 'trail' linear layer;
    // this group specifically controls the Pony Express station point markers.
    linearLayerKey: 'trail',
    stopLayerKey: 'pony_express',
    routes: ['Pony Express Route'],
  },
};
