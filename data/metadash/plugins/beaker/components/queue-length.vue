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
  name: 'beaker-queue-length',
  data () {
    return {
      title: 'Beaker Queue Length',
      loaded: false,
      chartData: {
        data: { },
        axis: { },
        grid: {
          y: {
            show: true
          }
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
          position: 'buttom'
        },
        size: {
          width: 800,
          height: 300
        },
        colors: archPalette
      }
    }
  },
  mounted () {
    this.$http.get('/api/beaker-queue-length')
      .then(res => res.json())
      .then(data => {
        this.chartData.bindto = this.$el
        this.chartData.axis = {
          x: {
            categories: (function () {
              var arr = ['Now']
              for (var i = 1, len = data.data[0].length; i < len - 1; i++) {
                arr.unshift(`${i} hours ago`)
              }
              return arr
            })(),
            type: 'category'
          }
        }
        this.chartData.data = {
          type: 'bar',
          columns: data.data
        }
        this.loaded = true
        this.chart = c3.generate(this.chartData)
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
