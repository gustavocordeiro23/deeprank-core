import os
from Bio.PDB.PDBParser import PDBParser
from Bio.PDB.ResidueDepth import ResidueDepth, get_surface, residue_depth
from Bio.PDB.HSExposure import HSExposureCA

import warnings
from Bio import BiopythonWarning

import tempfile

with warnings.catch_warnings():
    warnings.simplefilter('ignore',BiopythonWarning)
    from Bio import SearchIO

from time import time

def get_bio_model(sqldb):

    (f,name) = tempfile.mkstemp()
    sqldb.exportpdb(name)
    parser = PDBParser(PERMISSIVE=1)
    structure = parser.get_structure('_tmp',name)
    os.remove(name)
    return structure[0]

def get_depth_res(model):

    t0 = time()
    rd = ResidueDepth(model)
    print('__ Create RD %f' %(time()-t0))

    data = {}
    t0 = time()
    for k in list(rd.keys()):
        new_key = (k[0],k[1][1])
        data[new_key] = rd[k][0]
    print('__ Reformat RD %f' %(time()-t0))
    return data


def get_depth_contact_res(model,contact_res):

    surface = get_surface(model)
    data = {}
    for r in contact_res:
        chain = model[r[0]]
        res = chain[r[1]]
        data[r] = residue_depth(res,surface)
    return data

def get_hse(model):
    hse = HSExposureCA(model)
    data = {}
    for k in list(hse.keys()):
        new_key = (k[0],k[1][1])
        data[new_key] = hse[k]
    return data
