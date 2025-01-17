# necessary libraries
import re,urllib2
from bs4 import BeautifulSoup
from urllib import urlopen
import requests
import json
import pandas as pd
import math
import cgi
import jieba
import jieba.analyse
from glob import glob
import fileinput
from sklearn import feature_extraction
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.neighbors import NearestNeighbors
import re
from functools import partial
import cPickle
from annoy import AnnoyIndex
import time
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
import os
import cPickle as Pickle

# get the feature vectors from the whole data
def get_feature_vectors(source_dir = 'output/', pkl_dir='output/', mode = "batch"):
    if mode!="batch" and mode!="recent":
        print "Mode is wrong!"
        exit()

    msg_filename="news-id-tfidf50-topic-category.msg"
    
    if mode=="recent":
        msg_filename='recent-'+msg_filename
    
    if not os.path.exists(source_dir+msg_filename):
        print "[Error] No features available! Execute get_features.py first!"
        print "[Fallback] Get features from fallback.msg!"
        df = pd.read_msgpack('fallback/fallback.msg')
    else:
        df = pd.read_msgpack(source_dir+msg_filename)

    print "msg_filename: "+msg_filename
    fenci_str=[]
    print "number of rows:",len(df)
    
    for x in df['tags_text']:
        keys = ""
        for i in range(len(x)):
            keys = keys + str(x[i][0])
            if i!=len(x)-1:
                keys = keys + " "
        fenci_str.append(keys)
    #fenci_str=df['fenci_str'].tolist() 
    id_list = df['id'].tolist()

    #standard way to use TFIDF in scikit-learn
    print("Making Document Vectors...")
    
    transformer = TfidfTransformer()

    if mode=="batch":    
        cv = CountVectorizer()
        # get the vectorizer which fit 'fenci_str'
        term_doc = cv.fit_transform(fenci_str)
    else:
        # load countvectorizer
        if os.path.exists(pkl_dir+"cv.pkl"):
            f_pkl = open(pkl_dir+"cv.pkl","r")
        else:
            f_pkl = open("fallback/fallback-cv.pkl","r")
        cv = Pickle.load(f_pkl)    
        term_doc = cv.transform(fenci_str)    

    tfidf = transformer.fit_transform(term_doc)
    fv = tfidf.toarray()
    print len(fv[0])
 
    # save id_list and countvectorizer 
    if mode=="batch":
        f_pkl = open(pkl_dir+"cv.pkl",'w') 
        Pickle.dump(cv,f_pkl,True)
        f_pkl.close()
        f_id_list = open(pkl_dir+"id_list_all.pkl",'w')
        Pickle.dump(id_list, f_id_list, True)
        f_id_list.close()

    print("Done!")
    print "There are "+str(len(fv))+" feature vectors"   
    return fv, id_list

# weight: the feature vectors; id_list: the mapping between index and real id; dest: the output path
def ANN(fv,id_list,pkl_dir = 'output/', dest_dir='output/', mode="batch"):
    #start ann
    if not mode in ["batch","recent"]:
        print "[Error] Mode error!"
        exit()

    print("["+mode+"] Derive related news....")
    n = len(fv)
    f = len(fv[0])
    print("n="+str(n)+", f="+str(f)+"\n")

    print("Making Indexing Trees...")
    t = AnnoyIndex(f)  # Length of item vector that will be indexed
    for i in range(n):
        v = fv[i] 
        t.add_item(i,v)
        if i>=500 and i%500==0:
            print("Added...."+str(i))
    print("Build Indexing Trees....")
    t.build(5)

    # store the indexing tree
    tree_name = 'news-indexing-tree.ann'
    if mode=='recent':
        tree_name = 'recent-'+tree_name
    t.save(dest_dir + tree_name)
    print("Save indexing tree: "+ dest_dir + tree_name)
 
    # default generate 20 related news for each article
    # the result will be put into "output_filename"
    k=20
    output_filename='mirror-news-ann-distance-20.result'

    # t: the indexing tree for all data, t: the current indexing tree 
    if mode=="batch":
        pass
    elif mode=="recent":
        # 1. setting the output name 
        output_filename= 'recent-'+output_filename

        # 2. loading the indexing tree and id list of all data
        u = AnnoyIndex(f)
        # 2.1. Load indexing tree from all data
        if os.path.exists(dest_dir+"news-indexing-tree.ann"):
            print "Get the indexing tree: "+dest_dir+"news-indexing-tree.ann"
            u.load(dest_dir+"news-indexing-tree.ann")
        else:
            print "[Error] File does not exist:"+dest_dir+"news-indexing-tree.ann"
            print "Run ANN with batch mode first"
            exit()
        # 2.2. Load id list from all data
        if os.path.exists(pkl_dir+"id_list_all.pkl"):
            f_pkl = open(pkl_dir+"id_list_all.pkl",'r')
            id_list_all = Pickle.load(f_pkl)
        else:
            print "Failed to load: "+pkl_dir+"id_list_all.pkl"
            print "Load fallback id list"
            f_pkl = open("fallback/fallback-id-list-all.pkl","r")
            id_list_all = Pickle.load(f_pkl)

    g = open(dest_dir+output_filename,'w')
    pre_t = time.time()
    # generate a list for related news
    for i in range(n):
        news_id = id_list[i]
        
        knn_news = t.get_nns_by_item(i, k+1, include_distances=True)
        knn_list =  knn_news[0]
        dist_list = knn_news[1]
        del(knn_list[0])        
        del(dist_list[0])
        related_news = [(id_list[knn_list[j]],dist_list[j]) for j in range(len(knn_list))]

           
        if mode == "recent":
            vi = t.get_item_vector(i)
            knn_news_all = u.get_nns_by_vector(v, k, include_distances=True) 
            knn_list_all = knn_news_all[0]
            dist_list_all = knn_news_all[1]
            related_news_all = [(id_list_all[knn_list[j]],dist_list[j]) for j in range(len(knn_list))]
            # overwrite related_news
            
            for x in related_news_all:
                if not x[0] in knn_list:
                    related_news.append(x)
            # sort according to score
            related_news = sorted(related_news,key=lambda x:x[1])[0:k]

        related_news_json = json.dumps(related_news)
        g.write(news_id+"\t"+related_news_json+"\n")
        if i%100==0:
            print("Processed:"+str(i)+", time passed:"+str(time.time()-pre_t)+"(s)")
            pre_t=time.time()
    print "The related news are in: "+dest_dir+output_filename
    g.close() 

if __name__=="__main__":
    #get related news from all data
    fv,id_list =  get_feature_vectors(mode="batch")
    ANN(fv,id_list)

    # get related_news from recent data
    #fv,id_list =  get_feature_vectors(mode="recent")
    #ANN(fv,id_list,mode="recent")

