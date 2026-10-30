// Native OpenCFD2412 interface ordering; extends the point exporter pinned in
// PR37 at28d70e8. No pressure conversion or force model is implemented here.
#include "fvCFD.H"
#include "pointMesh.H"
#include "labelIOList.H"
#include "foamVersion.H"
#include <fstream>
#include <iomanip>

int main(int argc, char *argv[])
{
    #include "setRootCase.H"
    #include "createTime.H"
    #include "createMesh.H"
    const Foam::label patchi=mesh.boundaryMesh().findPatchID("wing");
    if (patchi<0) FatalErrorInFunction << "wing patch absent" << exit(FatalError);
    const Foam::pointMesh& pm=Foam::pointMesh::New(mesh);
    const Foam::labelList& ids=pm.boundary()[patchi].meshPoints();
    Foam::labelList pointGlobal(mesh.nPoints()), faceGlobal(mesh.nFaces());
    forAll(pointGlobal,i) pointGlobal[i]=i;
    forAll(faceGlobal,i) faceGlobal[i]=i;
    if (Foam::Pstream::parRun())
    {
        Foam::labelIOList pa(Foam::IOobject("pointProcAddressing",mesh.facesInstance(),Foam::polyMesh::meshSubDir,mesh,Foam::IOobject::MUST_READ,Foam::IOobject::NO_WRITE));
        Foam::labelIOList fa(Foam::IOobject("faceProcAddressing",mesh.facesInstance(),Foam::polyMesh::meshSubDir,mesh,Foam::IOobject::MUST_READ,Foam::IOobject::NO_WRITE));
        if(pa.size()!=mesh.nPoints() || fa.size()!=mesh.nFaces())
            FatalErrorInFunction << "Addressing size mismatch" << exit(FatalError);
        pointGlobal=pa;
        forAll(fa,i) faceGlobal[i]=Foam::mag(fa[i])-1;
        const auto& patch=mesh.boundaryMesh()[patchi];
        forAll(patch,i) if(fa[patch.start()+i]<=0)
            FatalErrorInFunction << "Unexpected reversed wing face addressing" << exit(FatalError);
    }
    Foam::labelList localIndex(mesh.nPoints(),-1);
    forAll(ids,i)
    {
        if(pointGlobal[ids[i]]<0) FatalErrorInFunction << "Invalid global point ID" << exit(FatalError);
        localIndex[ids[i]]=i;
    }
    const Foam::fileName path=runTime.path()/"interface.json";
    std::ofstream out(path.c_str());
    if(!out.good()) FatalErrorInFunction << "Cannot write " << path << exit(FatalError);
    out << std::setprecision(17);
    auto vec=[&out](const Foam::vector& p) {out << '[' << p.x() << ',' << p.y() << ',' << p.z() << ']';};
    out << "{\"schema_version\":1,\"axes\":[\"x_downstream\",\"y_spanwise\",\"z_up\"],"
        << "\"length_unit\":\"m\",\"area_unit\":\"m2\",\"reference_state\":\"exported_mesh\","
        << "\"patch\":\"wing\",\"rank\":" << Foam::Pstream::myProcNo()
        << ",\"time_s\":" << runTime.value() << ",\"native_runtime\":\"OpenCFD " << Foam::foamVersion::version << "\",\"point_ids\":[";
    forAll(ids,i) {if(i) out << ','; out << pointGlobal[ids[i]];}
    out << "],\"points_m\":[";
    forAll(ids,i) {if(i) out << ','; vec(mesh.points()[ids[i]]);}
    out << "],\"faces\":[";
    const auto& patch=mesh.boundaryMesh()[patchi];
    const auto& cf=mesh.Cf().boundaryField()[patchi];
    const auto& sf=mesh.Sf().boundaryField()[patchi];
    forAll(patch,i)
    {
        if(i) out << ',';
        const Foam::label facei=patch.start()+i;
        const Foam::face& face=mesh.faces()[facei];
        if(faceGlobal[facei]<0) FatalErrorInFunction << "Invalid global face ID" << exit(FatalError);
        out << "{\"id\":" << faceGlobal[facei] << ",\"point_indices\":[";
        forAll(face,j)
        {
            if(localIndex[face[j]]<0) FatalErrorInFunction << "Face point missing from native patch order" << exit(FatalError);
            if(j) out << ',';
            out << localIndex[face[j]];
        }
        out << "],\"center_m\":";vec(cf[i]);out << ",\"area_vector_m2\":";vec(sf[i]);out << '}';
    }
    out << "]}\n";out.close();
    if(!out.good()) FatalErrorInFunction << "Failed writing " << path << exit(FatalError);
    Foam::Info << "Exported " << ids.size() << " points and " << patch.size() << " faces to " << path << Foam::endl;
    return 0;
}
