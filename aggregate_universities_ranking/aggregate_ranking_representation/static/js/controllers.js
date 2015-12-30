'use strict';

/* Controllers */

var rankingApp = angular.module('rankingApp', []);


rankingApp.controller('RankingTableCtrl', function($scope, $http) {
    $scope.rankingTable = {headers : [], records : []};
    var prepareResponseDataToShow = function(responseData, scope) {
        console.log('Entry in prepareResponseDataToShow');
        var rankingTable = responseData['ranktable'];
        scope.rankingTable['headers'] = rankingTable[0];
        scope.rankingTable['records'] = rankingTable.slice(1);
    };
    $scope.requestData =  {selectedRankingNames : null, selectedYear : null}
    $scope.retrieveTableData = function(requestData) {
        console.log('retrieveTableData: $scope.requestData.selectedRankingNames: ' + $scope.requestData.selectedRankingNames + ', $scope.requestData.selectedYear: ' + $scope.requestData.selectedYear);
        $http({
            method : 'POST',
            url : 'api/table',
            data : requestData
        }).then(
            function successCallback(response) {
                console.log('retrieveTableData, success: ', response);
                $scope.table = response.data;
                prepareResponseDataToShow(response.data, $scope);
                //console.log('$scope.table[0]: ' + $scope.table[0].join(' '));
            },
            function errorrCallback(response) {
                console.log('retrieveTableData, error: ', response);
            }
        );
    }
    if ($scope.requestData.selectedRankingNames === null && $scope.requestData.selectedYear === null) {
        $scope.retrieveTableData($scope.requestData);
    }
});


rankingApp.controller('RankingCheckController', function($scope, $http) {
    var yearslist = [2014, 2015, 2016];
    yearslist.sort();
    yearslist.reverse();

    $scope.rankingchecklist  = [
        {name : 'QS', value : false},
        {name : 'THE', value : true},
        {name : 'NTU', value : false}
    ];

    $scope.yearsselect = {
        availableYears : [],
        selectedYear : {id : 0, value : 0}
    };
    
    var maxYear = 0;
    var maxYearId = 0;
    yearslist.forEach(function(year, i, yearslist) {
        $scope.yearsselect.availableYears.push({id : i, value : year});
        if (year > maxYear) {
            maxYear = year;
            maxYearId = i;
        }
    });
    $scope.yearsselect.selectedYear.id = maxYearId;
    $scope.yearsselect.selectedYear.value = maxYear;

    $scope.sendselected = function() {
        console.log('Entry in sendselected');
        var rankingchecklist = $scope.rankingchecklist;
        var selectednames = [];
        console.log('Sendselected: selectednames array declared');
        rankingchecklist.forEach(function(item, i, rankingchecklist) {
            if (item.value === true) {
                selectednames.push(item.name);
            }
        });
        console.log('Sendselected, selectednames: ' + selectednames.join(' '));
        $scope.requestData = {selectedRankingNames : selectednames, selectedYear : $scope.yearsselect.selectedYear.value}
        console.log('$scope.requestData.selectedRankingNames: ' + $scope.requestData.selectedRankingNames + ', $scope.requestData.selectedYear: ' + $scope.requestData.selectedYear);
        $scope.retrieveTableData($scope.requestData);
    };
});
