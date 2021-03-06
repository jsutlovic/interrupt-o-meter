function interrupt_bar_stacked(container, data){
    var d1 = data.done,
        d2 = data.started,
        d3 = data.planned,
        d4 = data.icebox,
        graph;

    graph = Flotr.draw(container, [
        { data: d1, label: "Done" },
        { data: d2, label: "Started" },
        { data: d3, label: "Planned" },
        { data: d4, label: "Icebox" },
    ], {
        colors: ['#4DA74D', '#C0D800', '#CCCCCC', '#00A8F0'],
        legend: {
            backgroundColor: "#FAFDFE",
        },
        xaxis: {
            noTicks: 3,
            min: -2,
            tickDecimals: 0,
            tickFormatter: function(val, config) {
                if (val == '0') {
                    return 'current';
                } else if (val == '1') {
                    return 'last';
                } else {
                    return '';
                }
            }
        },
        yaxis: {
            min: 0,
            tickDecimals: 0,
            tickFormatter: function(val, config) {
                var cur_num = parseInt(val);
                var max = 10;
                var red_val = Math.round(Math.min((cur_num/max)*255, 255)).toString(16);
                var ret = "<span style='color: #" + red_val + "0000'>" + cur_num + "</span>";
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

};


var update_page = function(days_since, interrupt_data) {
    $(".hotfix .days.current").text(days_since.hotfix.current.toFixed());
    $(".hotfix .days.max").text(days_since.hotfix.max.toFixed());

    $(".outage .days.current").text(days_since.outage.current.toFixed());
    $(".outage .days.max").text(days_since.outage.max.toFixed());

    interrupt_bar_stacked($('#interrupts_graph').get(0), interrupt_data);
}

$(function(){
    update_page(days_since, interrupt_data);

    $("a.reset.btn").click(function(e){
        e.preventDefault();

        var which = $(this).attr('href').replace('#', '');

        $.post(
            '/',
            {reset: which},
            function(data) {
                if (which == 'hotfix') {
                    days_since.hotfix.current = 0;
                } else if (which == 'outage') {
                    days_since.outage.current = 0;
                }

                update_page(days_since, interrupt_data);
            }
        );
    });

    $("a.update.btn").click(function(e){
        e.preventDefault();

        var which = $(this).attr('href').replace('#', '');

        $.post(
            '/',
            {update: which},
            function(data) {
                alert("Updated!: " + data);
                // Reload the page
                setTimeout(function(){location.reload(true);}, 300);
            }
        );
    });
});
