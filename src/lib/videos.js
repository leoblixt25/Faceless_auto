import {
  collection,
  addDoc,
  serverTimestamp,
  orderBy,
  query,
  limit,
  onSnapshot,
} from 'firebase/firestore'
import { db } from '../config/firebase'
import { VIDEO_STATUS } from '../utils/constants'

const videosCollection = collection(db, 'videos')

export async function createVideo({ userId, topic, platform, duration }) {
  const docRef = await addDoc(videosCollection, {
    userId,
    topic,
    platform,
    duration: duration || 30,
    status: VIDEO_STATUS.PENDING,
    createdAt: serverTimestamp(),
  })
  return docRef.id
}

export function subscribeToUserVideos(userId, onUpdate) {
  const q = query(
    videosCollection,
    orderBy('createdAt', 'desc'),
    limit(50),
  )

  const unsubscribe = onSnapshot(
    q,
    (snapshot) => {
      const videos = snapshot.docs
        .map((doc) => ({ id: doc.id, ...doc.data() }))
        .filter((video) => video.userId === userId)
      onUpdate(videos)
    },
    (error) => {
      console.error('Error subscribing to videos:', error)
    },
  )

  return unsubscribe
}
