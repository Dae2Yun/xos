
/*
 * Copyright 2017-present Open Networking Foundation

 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at

 * http://www.apache.org/licenses/LICENSE-2.0

 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */


/**
 * © OpenCORD
 *
 * Visit http://guide.xosproject.org/devguide/addview/ for more information
 *
 * Created by teone on 6/22/16.
 */

(function () {
  'use strict';

  describe('The Slices Encoder service', () => {

    let service, toscaBase, sliceQueryPromise, SliceSpy, rootScope;

    const toscaBaseDefault = {
      topology_template: {
        node_templates: {}
      }
    };

    const slicesArray = [
      {
        name: 'Slice1',
        description: 'Description1',
        network: 'noauto'
      },
      {
        name: 'Slice2',
        description: 'Description2',
        network: 'noauto'
      }
    ];

    const expected = {
      topology_template: {
        node_templates: {
          Slice1: {
            description: 'Description1',
            type: 'tosca.nodes.Slice',
            properties: {
              network: 'noauto'
            },
            requirements: [
              {management: {node: 'management', relationship: 'tosca.relationships.ConnectsToNetwork'}},
              {test_service: {node: 'service#test', relationship: 'tosca.relationships.MemberOfService'}}
            ]
          },
          Slice2: {
            description: 'Description2',
            type: 'tosca.nodes.Slice',
            properties: {
              network: 'noauto'
            },
            requirements: [
              {management: {node: 'management', relationship: 'tosca.relationships.ConnectsToNetwork'}},
              {test_service: {node: 'service#test', relationship: 'tosca.relationships.MemberOfService'}}
            ]
          }
        }
      }
    };

    beforeEach(module('xos.serviceGrid'));
    beforeEach(module('templates'));

    beforeEach(inject((SlicesEncoder, Slices, $q, $rootScope) => {
      toscaBase = angular.copy(toscaBaseDefault);
      service = SlicesEncoder;
      rootScope = $rootScope;

      sliceQueryPromise= $q.defer();
      SliceSpy = Slices;
      spyOn(SliceSpy, 'query').and.callFake(function(){
        return {$promise: sliceQueryPromise.promise};
      });
    }));
    
    describe('given a Slices array ', () => {
      it('should return the correct JSON structure', (done) => {
        service.buildTosca(slicesArray, toscaBase, 'test')
        .then(res => {
          expect(res).toEqual(expected);
          done();
        });
        rootScope.$apply();
      });
    });

    describe('given a service', () => {
      it('should return the JSON structure for all related slices', (done) => {
        service.getServiceSlices({id : 1, name: 'test'}, toscaBase)
        .then(res => {
          expect(res).toEqual(expected);
          done();
        });
        sliceQueryPromise.resolve(slicesArray);
        rootScope.$apply();
      });
    });
  });
})();

