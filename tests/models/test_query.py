import os
from tempfile import mkstemp

import numpy
import h5py

from deeprank_gnn.models.structure import Residue, Atom, AtomicElement
from deeprank_gnn.domain.amino_acid import alanine, phenylalanine, glutamine, arginine, asparagine
from deeprank_gnn.models.query import ProteinProteinInterfaceResidueQuery, SingleResidueVariantAtomicQuery
from deeprank_gnn.models.graph import Graph
from deeprank_gnn.domain.feature import *
from deeprank_gnn.tools.graph import graph_to_hdf5
from deeprank_gnn.DataSet import HDF5DataSet


def _check_graph_makes_sense(g, node_feature_names, edge_feature_names):

    assert len(g.nodes) > 0, "no nodes"
    assert FEATURENAME_POSITION in list(g.nodes.values())[0]

    assert len(g.edges) > 0, "no edges"
    assert FEATURENAME_EDGEDISTANCE in list(g.edges.values())[0]

    f, tmp_path = mkstemp(suffix=".hdf5")
    os.close(f)

    try:
        with h5py.File(tmp_path, 'w') as f5:
            graph_to_hdf5(g, f5)

        with h5py.File(tmp_path, 'r') as f5:
            entry_group = f5[list(f5.keys())[0]]

            for feature_name in node_feature_names:
                assert entry_group["node_data/{}".format(feature_name)][()].size > 0, "no {} feature".format(feature_name)

            assert entry_group["edge_index"][()].shape[1] == 2, "wrong edge index shape"

            assert entry_group["edge_index"].shape[0] > 0, "no edge indices"

            for feature_name in edge_feature_names:
                assert entry_group["edge_data/{}".format(feature_name)][()].shape[0] == entry_group["edge_index"].shape[0], \
                    "not enough edge {} feature values".format(feature_name)

            count_edges_hdf5 = entry_group["edge_index"].shape[0]

        dataset = HDF5DataSet(database=tmp_path)
        torch_data_entry = dataset[0]

        # expecting twice as many edges, because torch is directional
        count_edges_torch = torch_data_entry.edge_index.shape[1]
        assert count_edges_torch == 2 * count_edges_hdf5, "got {} edges in output data, hdf5 has {}".format(count_edges_torch, count_edges_hdf5)

        count_edge_features_torch = torch_data_entry.edge_attr.shape[0]
        assert count_edge_features_torch == count_edges_torch, "got {} edge feature sets, but {} edge indices".format(count_edge_features_torch, count_edges_torch)
    finally:
        os.remove(tmp_path)


def test_interface_graph():
    query = ProteinProteinInterfaceResidueQuery("tests/data/pdb/1ATN/1ATN_1w.pdb", "A", "B",
                                                {"A": "tests/data/pssm/1ATN/1ATN.A.pdb.pssm",
                                                 "B": "tests/data/pssm/1ATN/1ATN.B.pdb.pssm"})

    g = query.build_graph()

    _check_graph_makes_sense(g,
                             [FEATURENAME_POSITION,
                              FEATURENAME_CHARGE,
                              FEATURENAME_POLARITY,
                              FEATURENAME_PSSM,
                              FEATURENAME_INFORMATIONCONTENT],
                             [FEATURENAME_EDGEDISTANCE])


def test_variant_graph():
    query = SingleResidueVariantAtomicQuery("tests/data/pdb/101M/101M.pdb", "A", 27, None, asparagine, phenylalanine,
                                            {"A": "tests/data/pssm/101M/101M.A.pdb.pssm"},
                                            targets={"binclass": 0}, radius=20.0, nonbonded_distance_cutoff=20.0)

    g = query.build_graph()

    _check_graph_makes_sense(g,
                             [FEATURENAME_POSITION,
                              FEATURENAME_SASA,
                              FEATURENAME_PSSMDIFFERENCE],
                             [FEATURENAME_EDGEDISTANCE,
                              FEATURENAME_EDGEVANDERWAALS,
                              FEATURENAME_EDGECOULOMB])

    # Two negative nodes should result in positive coulomb potential
    # and less positive at longer distances:
    node_negative1 = "101M A 27 OD1"
    node_negative2 = "101M A 27 OD2"
    node_negative3 = "101M A 20 OD1"

    coulomb_close = g.edges[node_negative1, node_negative2][FEATURENAME_EDGECOULOMB]
    coulomb_far = g.edges[node_negative2, node_negative3][FEATURENAME_EDGECOULOMB]

    assert coulomb_close > 0, "two negative charges have been given negative coulomb potential"
    assert coulomb_far > 0, "two negative charges have been given negative coulomb potential"
    assert coulomb_close > coulomb_far, "two far away charges were given stronger coulomb potential than two close ones"

    # Two nodes of opposing charge should result in negative coulomb potential
    # and less negative at longer distances:
    node_positive1 = "101M A 31 CZ"

    coulomb_attract_close = g.edges[node_negative1, node_positive1][FEATURENAME_EDGECOULOMB]
    coulomb_attract_far = g.edges[node_negative3, node_positive1][FEATURENAME_EDGECOULOMB]

    assert coulomb_attract_close < 0, "two opposite charges were given positive coulomb potential"
    assert coulomb_attract_far < 0, "two opposite charges were given positive coulomb potential"
    assert coulomb_attract_close < coulomb_attract_far, "two far away charges were given stronger coulomb potential than two close ones"

    # If two atoms are further away from each other than their sigma values, then the LJ potential
    # should be negative and less negative at further distances.
    vanderwaals_close = g.edges[node_negative1, node_positive1][FEATURENAME_EDGEVANDERWAALS]
    vanderwaals_far = g.edges[node_negative3, node_positive1][FEATURENAME_EDGEVANDERWAALS]

    assert vanderwaals_close < 0, "vanderwaals potential is positive for two distant atoms"
    assert vanderwaals_far < 0, "vanderwaals potential is positive for two distant atoms"
    assert vanderwaals_close < vanderwaals_far, "two far atoms were given a stronger vanderwaals potential than two closer ones"

