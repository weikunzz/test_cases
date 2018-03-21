<template>
  <div>
    <div v-if="!loaded" class="text-center">
      <i class="fa fa-circle-o-notch fa-spin fa-3x fa-fw"></i>
      <span class="sr-only">Loading...</span>
    </div>
  </div>
</template>

<script>
import c3 from 'c3'
import pfPalette from '@/libs/patternfly-palette'

const archPalette = {
  aarch64: pfPalette.red,
  arm: pfPalette.yellow,
  armhfp: pfPalette.orange,
  i386: pfPalette.blue,
  ia64: pfPalette.pink,
  ppc64: pfPalette.lightGreen,
  ppc64le: pfPalette.green,
  s390: pfPalette.purple,
  s390x: pfPalette.purple300,
  x86_64: pfPalette.cyan
}

export default {
  name: 'beaker-statistics',
  data () {
    return {
      title: 'Bare-metal Systems',
      loaded: false,
      chartData: {
        donut: {
          title: 'Free Systems'
        },
        expand: true,
        label: {
          show: true
        },
        data: {
          colors: archPalette,
          type: 'donut',
          columns: []
        },
        tooltip: {
          format: {
            title: d => d,
            value: (value) => {
              return `${value} Systems`
            }
          }
        },
        legend: {
          show: true,
          position: 'right'
        },
        size: {
          width: 400,
          height: 300
        },
        sum: 0
      }
    }
  },
  mounted () {
    this.$http.get('/api/beaker-baremetal-free-systems')
      .then(res => res.json())
      .then(data => {
        this.chartData.sum = 0
        for (let i = 0, len = data.data.length; i < len; i++) {
          this.chartData.sum += data.data[i][1]
        }
        this.chartData.donut.title = `${this.chartData.sum} Free Systems`
        this.chartData.data.columns = data.data
        this.chartData.bindto = this.$el
        this.chart = c3.generate(this.chartData)
        this.loaded = true
      })
  }
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style>
.c3-tooltip {
  color: white;
}
</style>
