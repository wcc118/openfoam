/* global vtk */
'use strict';
(() => {
const $ = id => document.getElementById(id);
try {
 const data=JSON.parse($('flow-data').textContent), m=data.metadata;
 $('title').textContent=m.title;
 $('scope').textContent=`${m.alpha_deg}° · steady iteration ${m.steady_iteration} · not physical time`;
 $('provenance').textContent=JSON.stringify(m.provenance,null,2);
 for(const s of m.limitations){const li=document.createElement('li');li.textContent=s;$('limitations').append(li);}
 $('method').textContent='Paths follow saved 3D velocity. Q surface shows the supplied threshold geometry. Volume colors the supplied 3D grid; absent samples are transparent. Speed range is fixed for every layer.';
 const generic=vtk.Rendering.Misc.vtkGenericRenderWindow.newInstance({background:[.065,.11,.17]});
 generic.setContainer($('render-container'));generic.resize();
 const renderer=generic.getRenderer(),renderWindow=generic.getRenderWindow();
 const color=vtk.Rendering.Core.vtkColorTransferFunction.newInstance();
 [[0,.133,.388,.941],[15,0,.855,.918],[30,.992,.945,.039],[45,.961,.188,.188]].forEach(p=>color.addRGBPoint(...p));
 function poly(part,kind,location){
  const p=vtk.Common.DataModel.vtkPolyData.newInstance();p.getPoints().setData(new Float32Array(part.points),3);
  (kind==='lines'?p.getLines():p.getPolys()).setData(new Uint32Array(part[kind]));
  if(location){const scalar=vtk.Common.Core.vtkDataArray.newInstance({name:'Speed',numberOfComponents:1,values:new Float32Array(part.speed)});(location==='cell'?p.getCellData():p.getPointData()).setScalars(scalar);}
  return p;
 }
 function surface(part,kind,location){
  const input=poly(part,kind,location),mapper=vtk.Rendering.Core.vtkMapper.newInstance();
  if(kind==='lines'){
   const tubes=vtk.Filters.General.vtkTubeFilter.newInstance({radius:.0012,numberOfSides:6,capping:true});tubes.setInputData(input);tubes.setInputArrayToProcess(0,'Speed','PointData','Scalars');mapper.setInputConnection(tubes.getOutputPort());
  }else mapper.setInputData(input);
  mapper.setScalarVisibility(Boolean(location));
  if(location){mapper.setLookupTable(color);mapper.setScalarRange(0,45);mapper.setColorModeToMapScalars();location==='cell'?mapper.setScalarModeToUseCellData():mapper.setScalarModeToUsePointData();}
  const actor=vtk.Rendering.Core.vtkActor.newInstance();actor.setMapper(mapper);renderer.addActor(actor);return actor;
 }
 const actors={wing:surface(data.wing,'polys'),paths:surface(data.paths,'lines','point'),vortex:surface(data.vortex,'polys','cell')};
 actors.wing.getProperty().setColor(.62,.67,.73);actors.wing.getProperty().setAmbient(.3);
 actors.vortex.getProperty().setOpacity(.7);actors.vortex.getProperty().setAmbient(.35);
 const image=vtk.Common.DataModel.vtkImageData.newInstance();image.setDimensions(...data.volume.dimensions);image.setOrigin(...data.volume.origin);image.setSpacing(...data.volume.spacing);
 image.getPointData().setScalars(vtk.Common.Core.vtkDataArray.newInstance({name:'Speed',numberOfComponents:1,values:new Float32Array(data.volume.speed)}));
 const vm=vtk.Rendering.Core.vtkVolumeMapper.newInstance();vm.setInputData(image);vm.setSampleDistance(Math.min(...data.volume.spacing)/2);
 const volume=vtk.Rendering.Core.vtkVolume.newInstance();volume.setMapper(vm);actors.volume=volume;
 const opacity=vtk.Common.DataModel.vtkPiecewiseFunction.newInstance();
 function updateOpacity(){const scale=Number($('volume-opacity').value)/30;opacity.removeAllPoints();const knots=$('hide-freestream').checked?[[-1,0],[0,0],[10,.04],[25,.025],[29,0],[31,0],[35,.04],[45,.08]]:[[-1,0],[0,0],[10,.01],[30,.025],[45,.06]];knots.forEach(([x,y])=>opacity.addPoint(x,Math.min(1,y*scale)));}
 updateOpacity();volume.getProperty().setRGBTransferFunction(0,color);volume.getProperty().setScalarOpacity(0,opacity);volume.getProperty().setScalarOpacityUnitDistance(0,.01);volume.getProperty().setInterpolationTypeToNearest();volume.getProperty().setShade(false);volume.setVisibility(false);renderer.addVolume(volume);
 const camera=renderer.getActiveCamera();
 function overview(){camera.setPosition(2.1,1.9,1.35);camera.setFocalPoint(.48,0,.03);camera.setViewUp(0,0,1);renderer.resetCamera();camera.zoom(1.35);renderer.resetCameraClippingRange();renderWindow.render();}
 function tip(){camera.setPosition(1.0,1.05,.4);camera.setFocalPoint(.28,.59,.035);camera.setViewUp(0,0,1);camera.setViewAngle(30);renderer.resetCameraClippingRange();renderWindow.render();}
 for(const key of Object.keys(actors))$('show-'+key).onchange=()=>{actors[key].setVisibility($('show-'+key).checked);renderer.resetCameraClippingRange();renderWindow.render();};
 $('surface-opacity').oninput=()=>{actors.vortex.getProperty().setOpacity(Number($('surface-opacity').value)/100);renderWindow.render();};
 $('hide-freestream').onchange=()=>{updateOpacity();renderWindow.render();};
 $('volume-opacity').oninput=()=>{updateOpacity();renderWindow.render();};
 $('reset-btn').onclick=overview;$('tip-btn').onclick=tip;
 window.addEventListener('resize',()=>generic.resize());
 window.flow3dTest={renderer,renderWindow,actors,data,opacity,generic};overview();
}catch(error){$('error').textContent='Unable to render 3D flow. WebGL2 support is required. '+error.message;console.error(error);}
})();
