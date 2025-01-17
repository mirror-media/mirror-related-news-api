from redis import Redis
import os
import pandas as pd
import json

# this is for docker
r = Redis(host='redis',port=6379)

def load_data(r):
    if os.path.exists('output/mirror-news-ann-distance-20.result')==True:
        f = open('output/mirror-news-ann-distance-20.result','r')
    else:
        print("[Warning] Cannot find the latest list of related news. Use the fallback list now. Please run daily_batch.sh to get the latest related news")
        f = open('fallback.result','r')
    
    news_dict = dict()
    
    if os.path.exists('output/news_id_tfidf50_topic_category.msg')==True:
        df = pd.read_msgpack('output/news_id_tfidf50_topic_category.msg')
    else:
        print("[Warning] Cannot find the latest metadata of related news. Use the fallback metadata now. Please run daily_batch.sh to get the latest metadata")
        df = pd.read_msgpack('fallback.msg')

    print("Loading the KNN list...")
    for line in f:
        news_id, knn_raw = line.replace("\n","").split("\t")
        knn_list = json.loads(knn_raw)
        news_dict[news_id] = dict()
        news_dict[news_id]['knn_list']=knn_list
        
        this_df = df[df.id==news_id]
        n_cat = (this_df.category).tolist()
        n_title = (this_df.title).tolist()[0]
        n_features = (this_df.tags_50_text).tolist()

        news_dict[news_id]['title']=n_title
        news_dict[news_id]['category']=n_cat
        news_dict[news_id]['features']=n_features
        news_dict[news_id]['url']="https://api.mirrormedia.mg/posts/"+news_id
  
    print "Total: "+str(len(news_dict))    
    print "Feed all to Redis..."
    r.hmset('news_dict',news_dict)
    print "Done!" 

if __name__=="__main__":
    load_data(r)
    
     



