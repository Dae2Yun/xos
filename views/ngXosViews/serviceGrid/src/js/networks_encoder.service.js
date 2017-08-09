
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

  /**
   * @ngdoc service
   * @name xos.NetworkEncoder.serviceGrid
   **/

  // TODO write tests
  angular.module('xos.serviceGrid')
    .service('NetworkEncoder', function($q, Networks, NetworkTemplateEncoder){

      this.buildTosca = (networks, toscaSpec) => {

        const apiNetworks = angular.copy(networks);

        // store here the promise that will build the dependency structure
        let dependency = {
        };

        const d = $q.defer();

        try {
          networks = _.reduce(networks, (obj, n) => {
            obj[`network#${n.name}`] = {
              type: 'tosca.nodes.network.Network.XOS',
              requirements: []
            };

            // for each network slice, add requirement
            if(angular.isDefined(n.slices)) {
              _.forEach(n.slices, s => {
                let owner = {
                  owner: {
                    node: s.name,
                    relationship: 'tosca.relationships.MemberOfSlice'
                  }
                };

                let conn =  {
                  connection: {
                    node: s.name,
                    relationship: 'tosca.relationships.ConnectsToSlice'
                  }
                };
                obj[`network#${n.name}`].requirements.push(owner, conn);
              });

              if(angular.isDefined(n.template)){
                dependency[n.name] = NetworkTemplateEncoder.buildTosca(n.template, toscaSpec);
              }
            }

            return obj;

          }, {});

          // if we have dependency wait for them
          if(Object.keys(dependency).length > 0){
            $q.all(dependency)
            .then(deps => {
              // NOTE how to make this readable??
              if(deps){

                // for each property in deps
                for(let k of Object.keys(deps)){
                  let [tosca, template] = deps[k];
                  networks[`network#${k}`].requirements.push({
                    network_template: {
                      node: `network_template#${template.name}`,
                      relationship: 'tosca.relationships.UsesNetworkTemplate'
                    }
                  });
                  angular.extend(toscaSpec, tosca);
                }
              }
              angular.extend(toscaSpec.topology_template.node_templates, networks);
              d.resolve([toscaSpec, apiNetworks]);
            })
            .catch(e => {
              throw new Error(e);
            });
          }
          //else resolve directly
          else {
            angular.extend(toscaSpec.topology_template.node_templates, networks);
            d.resolve([toscaSpec, apiNetworks]);
          }
        }
        catch(e){
          d.reject(e);
        }

        return d.promise;
      };

      this.getSliceNetworks = (slice, toscaSpec) => {
        const d = $q.defer();
        Networks.query({owner: slice.id}).$promise
        .then((networks) => {
          // check that all the network this slice own are listed in the slice
          // does this make sense?
          networks = _.filter(networks, n => {
            return slice.networks.indexOf(n.id) !== -1;
          });

          // denormalize slice inside network
          networks = networks.map(n => {
            let idx = n.slices.indexOf(slice.id);
            n.slices[idx] = slice;
            return n;
          });

          this.buildTosca(networks, toscaSpec)
          .then(d.resolve)
          .catch(d.reject);

        });

        return d.promise;
      }
    });
})();

