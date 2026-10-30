#include "fvCFD.H"
#include "pointMesh.H"
#include "OFstream.H"
int main(int argc, char *argv[])
{
    #include "setRootCase.H"
    #include "createTime.H"
    #include "createMesh.H"
    const label patchi=mesh.boundaryMesh().findPatchID("wing");
    if (patchi<0) FatalErrorInFunction << "wing patch absent" << exit(FatalError);
    const pointMesh& pm=pointMesh::New(mesh);
    const labelList& ids=pm.boundary()[patchi].meshPoints();
    OFstream output(runTime.path()/"wing-points.dat");
    output.precision(17);
    output << ids.size() << nl;
    forAll(ids,i)
    {
        const point& p=mesh.points()[ids[i]];
        output << ids[i] << ' ' << p.x() << ' ' << p.y() << ' ' << p.z() << nl;
    }
    Info << "Exported " << ids.size() << " native point-patch coordinates" << endl;
    return 0;
}
