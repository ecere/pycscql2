# (CartoSym) CQL2
A Free and Open-Source Software library implementing [OGC Common Query Language (CQL2)](https://www.opengis.net/doc/IS/cql2/1.0),
including extensions introduced in [OGC Cartographic Symbology 2.0](https://github.com/opengeospatial/cartographic-symbology).

libCartoSym's [_libCQL2_](https://github.com/ecere/libCartoSym/tree/main/CQL2) dependency provides support for
parsing and writing CQL2-Text and CQL2-JSON expressions, which themselves imply support for parsing and writing geometries defined in
[Well-Known Text (WKT)](http://portal.opengeospatial.org/files/?artifact_id=25355) and [GeoJSON](https://tools.ietf.org/rfc/rfc7946.txt) which is provided by
[_libSFGeometry_](https://github.com/ecere/libCartoSym/tree/main/SFGeometry) and [_libSFCollections_](https://github.com/ecere/libCartoSym/tree/main/SFCollections).
The ability to perform spatial relation queries based on the [Dimensionally Extended-9 Intersection Model](https://en.wikipedia.org/wiki/DE-9IM) is provided by [_libDE9IM_](https://github.com/ecere/libCartoSym/tree/main/DE9IM).
The [_libGeoExtents_](https://github.com/ecere/libCartoSym/tree/main/GeoExtents) library provides the foundational basic data structures for geographic points and extents.

Additional functionality includes run-time evaluation of expressions.

Object-oriented bindings for _libCQL2_ automatically generated using Ecere's [binding generating tool (bgen)](https://github.com/ecere/bgen) from the eC library will be available
for the C, C++ and Python programming languages, with eventual support for Java, Rust and JavaScript planned as well.
