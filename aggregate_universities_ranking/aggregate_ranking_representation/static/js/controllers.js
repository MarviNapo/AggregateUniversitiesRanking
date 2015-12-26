'use strict';

/* Controllers */

var rankingApp = angular.module('rankingApp', []);

rankingApp.controller('RankingListCtrl', function($scope, $http) {
    $scope.name = 'World';
    $scope.rankinglist = [
        {'name' : 'QS'},
        {'name' : 'THE'}
    ];
    $http.get('api/table?format=json').success(function(data) {
        $scope.table = data;
    });
});

