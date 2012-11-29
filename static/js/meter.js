(function interrupt_bar_stacked(container, data){
    var d1 = data.done,
        d2 = data.started,
        d3 = data.planned,
        d4 = data.icebox,
        graph;

    graph = Flotr.draw(container, [
        { data: d4, label: "Icebox" },
        { data: d3, label: "Planned" },
        { data: d2, label: "Started" },
        { data: d1, label: "Done" },
    ], {
        colors: ['#00A8F0', '#CCCCCC', '#C0D800', '#4DA74D'],
        legend: {
            backgroundColor: "#FAFDFE",
        },
        xaxis: {
            noTicks: 0,
        },
        yaxis: {
            min: 0,
            tickDecimals: 0,
            tickFormatter: function(val, config) {
                var cur_num = parseInt(val);
                var max = 10;
                var red_val = Math.round(Math.min((cur_num/max)*255, 255)).toString(16);
                var ret = "<span style='color: #" + red_val + "0000'>" + cur_num + "</span>";
                console.log(ret);
                return ret;
            }
        },
        bars: {
            show: true,
            stacked: true,
            horizontal: false,
            barWidth: 0.8,
            lineWidth: 1,
            shadowSize: 0,
        },
        grid: {
            verticalLines: false,
            horizontalLines: true,
        }
    });

});//($('#interrupts_graph').get(0), interrupt_data);


$(function(){
    $(".hotfix .days.current").text(days_since.hotfix.current.toFixed());
    $(".hotfix .days.max").text(days_since.hotfix.max.toFixed());

    $(".outage .days.current").text(days_since.outage.current.toFixed());
    $(".outage .days.max").text(days_since.outage.max.toFixed());
});
