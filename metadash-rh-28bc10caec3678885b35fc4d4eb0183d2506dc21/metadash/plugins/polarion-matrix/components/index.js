import app from './app.vue'

export default {
  path: 'polarion-matrix', // Need to be uniq, and will be used for url routing
  icon: '<i class="fa fa-map-signs" aria-hidden="true"></i>', // Or import a webpack resource
  entry: app,
  title: 'Polarion Matrix'
}
