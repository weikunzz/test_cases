<template>
  <div class="cards-pf container-fluid container-cards-pf">
    <div class="row row-cards-pf">
      <div class="col-xs-4">
        <pf-card title="Free Bare Systems">
          <free-bare-system>
          </free-bare-system>
        </pf-card>
      </div>
      <div class="col-xs-8">
        <pf-card title="Beaker Queue Length">
          <beaker-queue-length>
          </beaker-queue-length>
        </pf-card>
      </div>
    </div>
  </div>
</template>

<script>
import FreeBareSystem from './free-bare-system'
import BeakerQueueLength from './queue-length.vue'

export default {
  name: 'beaker-statistics',
  components: { FreeBareSystem, BeakerQueueLength },
  data () {
    return {}
  },
  mounted () {
  }
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
